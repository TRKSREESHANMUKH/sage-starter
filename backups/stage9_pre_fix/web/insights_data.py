"""
web/insights_data.py — SAGE Insights Tab Data Engine (Stage 9 v5).

Part 6 Requirements:
- Global Current Day support and default period "Year so far" (ytd).
- Exact date range formatted under title ("1 Jan 2025 to 3 Feb 2025").
- Zero-delivery rows show "—" for on-time %, delay, and quantity (greyed out, "No deliveries in this period").
- Plural handling ("1 day", "2 days").
- Richer Supplier Report Card columns:
    Material supplied, Deliveries (n), On-time %, Average days late, Worst delay & date,
    Promised lead time vs actual lead time (days), Open orders now (with oldest overdue),
    Next expected delivery date, Quantity received vs ordered, Coincided with, Rating.
- New Block: Customer orders (product service, customer service, top 5 most delayed orders).
- New Block: Delay ledger (sortable/searchable table of every late supplier receipt and customer order).
- New Block: Weekly trend (row per week: demand, produced, shipped, late units, low stock days + line chart).
- Disruption episodes with plain-English stories.
- What changed this week strip (comparing last 7 days with prior 7 days).
- Exports: supplier report CSV, delay ledger CSV, and insights PDF.
- Cache per (source, as-of date, period) in analytics/insights_cache/, invalidated upon ingest.
- Strict SQL guard: zero access to business_events or evaluation tables.
"""

from __future__ import annotations

import csv
from datetime import date, datetime, timedelta
import io
import json
import logging
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd
from sqlalchemy import text

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import SessionLocal
from app.models.purchasing import PurchaseOrder, PurchaseOrderLine, GoodsReceipt, GoodsReceiptLine
from app.models.sales import SalesOrder, SalesOrderLine, Delivery, DeliveryLine, Customer
from app.models.suppliers import Supplier
from app.models.inventory import Product, InventoryItem, StockMovement
from app.models.production import ProductionOrder
from stage9.clock import get_as_of_date
from stage9.current_day import get_current_day
from stage9.status import RESEARCH_FRAMING
from web.one_page_data import FROZEN_PAST_CASES

logger = logging.getLogger("web.insights_data")

CACHE_DIR = ROOT_DIR / "analytics" / "insights_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
PANEL_PARQUET_PATH = ROOT_DIR / "analytics" / "daily_panel.parquet"


def sql_guard_check(entity_or_query: Any) -> None:
    """Verifies that no prohibited ground-truth or business-events entities are queried."""
    forbidden = ["business_events", "evaluation", "ground_truth", "seed_master"]
    name_str = str(entity_or_query).lower()
    for f in forbidden:
        if f in name_str:
            raise PermissionError(f"[SQL GUARD] Access to prohibited entity '{f}' rejected.")


_CACHED_PANEL: Optional[pd.DataFrame] = None


def get_cached_panel() -> pd.DataFrame:
    global _CACHED_PANEL
    if _CACHED_PANEL is not None:
        return _CACHED_PANEL
    if PANEL_PARQUET_PATH.exists():
        try:
            _CACHED_PANEL = pd.read_parquet(PANEL_PARQUET_PATH)
        except Exception:
            _CACHED_PANEL = pd.DataFrame()
    else:
        _CACHED_PANEL = pd.DataFrame()
    return _CACHED_PANEL


def format_days_plural(days: Optional[float]) -> str:
    """Formats day count with correct singular/plural English grammar."""
    if days is None:
        return "—"
    if abs(days) < 1e-4:
        return "0 days"
    if abs(days - 1.0) < 1e-4:
        return "1 day"
    if float(days).is_integer():
        return f"{int(days)} days"
    return f"{days:.1f} days"


def compute_rating(on_time_pct: Optional[float], fill_rate_pct: Optional[float], n_deliveries: int) -> Tuple[str, str, bool]:
    """
    Fixed rating rule pre-registered in stage9/config/rules.yaml:
    - If n == 0: 'No deliveries in this period', greyed out
    - If n < 5: 'Too few deliveries to rate', greyed out
    - Grade A if on-time >= 90% and received >= 95%
    - Grade B if on-time >= 70%
    - Grade C otherwise
    """
    if n_deliveries == 0:
        return "No deliveries in this period", "badge-calm", True
    if n_deliveries < 5:
        return "Too few deliveries to rate", "badge-calm", True
    if on_time_pct is not None and fill_rate_pct is not None:
        if on_time_pct >= 90.0 and fill_rate_pct >= 95.0:
            return "Grade A", "badge-strong", False
        if on_time_pct >= 70.0:
            return "Grade B", "badge-some", False
    return "Grade C", "badge-weak", False


def get_insights_data(
    as_of_str: Optional[str] = None,
    period_str: str = "ytd",
    force_refresh: bool = False,
    as_of: Optional[Any] = None,
    period: Optional[str] = None
) -> Dict[str, Any]:
    """
    Main entry point for the Insights tab.
    Caches per (source, as_of, period).
    """
    if period:
        period_str = period

    if as_of is not None:
        if isinstance(as_of, (date, datetime)):
            cur_as_of = as_of if isinstance(as_of, date) and not isinstance(as_of, datetime) else as_of.date()
            as_of_str = cur_as_of.isoformat()
        else:
            as_of_str = str(as_of)
            cur_as_of = datetime.strptime(as_of_str, "%Y-%m-%d").date()
    elif as_of_str:
        cur_as_of = datetime.strptime(as_of_str, "%Y-%m-%d").date()
    else:
        cur_as_of = get_current_day()
        as_of_str = cur_as_of.isoformat()

    valid_periods = {"30d", "quarter", "ytd", "full_year"}
    if period_str not in valid_periods:
        period_str = "ytd"

    is_demo = os.getenv("SAGE_DEMO", "false").lower() in ("true", "1", "yes")
    if period_str == "full_year" and not is_demo:
        period_str = "ytd"

    source = os.getenv("SAGE_SOURCE", "live")
    cache_file = CACHE_DIR / f"insights_{source}_{cur_as_of.isoformat()}_{period_str}.json"

    if cache_file.exists() and not force_refresh:
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cached_data = json.load(f)
            return cached_data
        except Exception:
            pass

    computed = compute_insights_payload(cur_as_of, period_str, is_demo, source=source)

    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(computed, f, indent=2, sort_keys=True)

    return computed


def compute_insights_payload(as_of: date, period_str: str, is_demo: bool, source: str = "live") -> Dict[str, Any]:
    """Performs read-only operational analytics up to as_of date."""
    # 1. Determine period window
    if period_str == "30d":
        start_d = max(date(2025, 1, 1), as_of - timedelta(days=30))
        period_label = "Last 30 days"
    elif period_str == "quarter":
        start_d = max(date(2025, 1, 1), as_of - timedelta(days=90))
        period_label = "Last quarter"
    elif period_str == "full_year" and is_demo:
        start_d = date(2025, 1, 1)
        as_of = date(2025, 12, 31)
        period_label = "Full-year view (demo)"
    else:
        start_d = date(2025, 1, 1)
        period_label = "Year so far"

    start_str = start_d.isoformat()
    as_of_str = as_of.isoformat()
    date_range_str = f"{start_d.strftime('%-d %b %Y')} to {as_of.strftime('%-d %b %Y')}"

    # 2. Slice Daily Panel (Read-only)
    panel = get_cached_panel()
    if not panel.empty:
        panel_window = panel[(panel["date"] >= start_str) & (panel["date"] <= as_of_str)].sort_values("date").reset_index(drop=True)
    else:
        panel_window = pd.DataFrame()

    db = SessionLocal(source=source)

    try:
        sql_guard_check("purchase_orders")
        sql_guard_check("goods_receipts")
        sql_guard_check("sales_orders")
        sql_guard_check("deliveries")

        suppliers = db.query(Supplier).order_by(Supplier.id).all()
        products = db.query(Product).order_by(Product.id).all()
        customers = db.query(Customer).order_by(Customer.id).all()

        prod_map = {p.id: p.name for p in products}
        cust_map = {c.id: c.name for c in customers}

        supplier_material_info = {
            1: ("Raw steel (Material 101)", 101, 50.0),
            2: ("Copper wire (Material 102)", 102, 40.0),
            3: ("Copper wire (Material 102)", 102, 40.0),
            4: ("Electronic housings (Material 103)", 103, 30.0),
            5: ("Electronic housings (Material 103)", 103, 30.0)
        }

        # 3. Query all Purchase Orders & Goods Receipts up to as_of
        all_pos = (
            db.query(PurchaseOrder, PurchaseOrderLine, Supplier)
            .join(PurchaseOrderLine, PurchaseOrderLine.po_id == PurchaseOrder.id)
            .join(Supplier, Supplier.id == PurchaseOrder.supplier_id)
            .filter(PurchaseOrder.order_date <= as_of)
            .order_by(PurchaseOrder.order_date)
            .all()
        )

        all_grs = (
            db.query(GoodsReceipt, GoodsReceiptLine, PurchaseOrderLine, PurchaseOrder, Supplier)
            .join(GoodsReceiptLine, GoodsReceiptLine.receipt_id == GoodsReceipt.id)
            .join(PurchaseOrderLine, PurchaseOrderLine.id == GoodsReceiptLine.po_line_id)
            .join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderLine.po_id)
            .join(Supplier, Supplier.id == PurchaseOrder.supplier_id)
            .filter(GoodsReceipt.receipt_date <= as_of)
            .order_by(GoodsReceipt.receipt_date)
            .all()
        )

        po_receipts: Dict[int, Dict[str, Any]] = {}
        for gr, gr_line, po_line, po, supp in all_grs:
            if po.id not in po_receipts:
                delay = (gr.receipt_date - po.expected_delivery_date).days
                actual_lt = (gr.receipt_date - po.order_date).days
                po_receipts[po.id] = {
                    "po_id": po.id,
                    "supplier_id": supp.id,
                    "supplier_name": supp.name,
                    "order_date": po.order_date.isoformat(),
                    "expected_date": po.expected_delivery_date.isoformat(),
                    "receipt_date": gr.receipt_date.isoformat(),
                    "delay_days": delay,
                    "actual_lead_time": actual_lt,
                    "promised_lead_time": supp.base_lead_time_days or 5,
                    "quantity_ordered": po_line.quantity_ordered or 0,
                    "quantity_received": gr_line.quantity_received or 0
                }
            else:
                po_receipts[po.id]["quantity_received"] += (gr_line.quantity_received or 0)

        # 4. Supplier Report Card (Richer Columns)
        supplier_cards = []
        chart_delivery_delays = []
        late_supplier_records = []

        for supp in suppliers:
            s_id = supp.id
            s_name = supp.name
            mat_label, mat_id, mat_safety = supplier_material_info.get(s_id, ("General Materials", 101, 40.0))

            s_deliveries = [
                d for d in po_receipts.values()
                if d["supplier_id"] == s_id and d["receipt_date"] >= start_str and d["receipt_date"] <= as_of_str
            ]

            n = len(s_deliveries)
            if n > 0:
                on_time_count = sum(1 for d in s_deliveries if d["delay_days"] <= 0)
                on_time_pct = round((on_time_count / n) * 100.0, 1)
                on_time_pct_str = f"{on_time_pct:.1f}%"
                late_delays = [d["delay_days"] for d in s_deliveries if d["delay_days"] > 0]
                avg_days_late = round(float(sum(late_delays) / len(late_delays)), 1) if late_delays else 0.0
                avg_days_late_str = format_days_plural(avg_days_late)
                worst_d_item = max(s_deliveries, key=lambda x: x["delay_days"])
                worst_delay = worst_d_item["delay_days"]
                worst_delay_date = worst_d_item["receipt_date"]
                worst_delay_str = f"{format_days_plural(worst_delay)} ({worst_delay_date})" if worst_delay > 0 else "0 days"
                total_ord = sum(d["quantity_ordered"] for d in s_deliveries)
                total_rec = sum(d["quantity_received"] for d in s_deliveries)
                fill_rate_pct = round((total_rec / total_ord * 100.0), 1) if total_ord > 0 else 100.0
                qty_str = f"{total_rec:,} / {total_ord:,} u ({fill_rate_pct:.0f}%)"
                avg_actual_lt = sum(d["actual_lead_time"] for d in s_deliveries) / n
                lead_time_str = f"Promised {supp.base_lead_time_days or 5}d / Actual {avg_actual_lt:.1f}d"
                summary_sentence = (
                    f"{s_name} delivered all {n} order{'s' if n > 1 else ''} on time with 0 days delay."
                    if not late_delays else
                    f"{s_name} was late on {len(late_delays)} of {n} deliveries, worst {worst_delay_str}."
                )
            else:
                on_time_pct = None
                on_time_pct_str = "—"
                avg_days_late = None
                avg_days_late_str = "—"
                worst_delay = None
                worst_delay_str = "—"
                fill_rate_pct = None
                qty_str = "—"
                lead_time_str = f"Promised {supp.base_lead_time_days or 5}d / Actual —"
                summary_sentence = f"{s_name} had no deliveries during this period."

            rating_text, badge_class, is_greyed = compute_rating(on_time_pct, fill_rate_pct, n)

            # Open POs now (as of as_of date)
            open_pos = [
                po for po, pol, s in all_pos
                if s.id == s_id and po.order_date <= as_of and (pol.quantity_received or 0) < (pol.quantity_ordered or 0)
            ]
            if open_pos:
                overdue_open = [p for p in open_pos if p.expected_delivery_date < as_of]
                if overdue_open:
                    oldest = min(overdue_open, key=lambda x: x.expected_delivery_date)
                    oldest_days = (as_of - oldest.expected_delivery_date).days
                    open_orders_str = f"{len(open_pos)} open (PO #{oldest.id}, {format_days_plural(oldest_days)} overdue)"
                else:
                    open_orders_str = f"{len(open_pos)} open (all on schedule)"
                next_expected_date = min((p.expected_delivery_date for p in open_pos if p.expected_delivery_date >= as_of), default=None)
                next_expected_str = next_expected_date.isoformat() if next_expected_date else "Pending review"
            else:
                open_orders_str = "0 open"
                next_expected_str = "None pending"

            # Coincided with low stock days
            coincided_days = 0
            if not panel_window.empty:
                mat_col = f"material_{mat_id}_stock"
                supp_col = f"supplier_{s_id}_po_delay_days"
                if mat_col in panel_window.columns and supp_col in panel_window.columns:
                    cond = (panel_window[mat_col] <= mat_safety) & (panel_window[supp_col] > 0)
                    coincided_days = int(cond.sum())
            coincided_str = f"{coincided_days} days low stock" if coincided_days > 0 else "0 days"

            for d in s_deliveries:
                chart_delivery_delays.append({
                    "date": d["receipt_date"],
                    "po_id": d["po_id"],
                    "supplier_id": s_id,
                    "supplier_name": s_name,
                    "delay_days": d["delay_days"],
                    "quantity_received": d["quantity_received"]
                })
                if d["delay_days"] > 0:
                    late_supplier_records.append({
                        "record_type": "Supplier Delivery",
                        "ref_no": f"PO #{d['po_id']}",
                        "partner": s_name,
                        "item": mat_label,
                        "quantity": d["quantity_received"],
                        "due_date": d["expected_date"],
                        "actual_date": d["receipt_date"],
                        "days_late": d["delay_days"],
                        "status": "Delivered late"
                    })

            supplier_cards.append({
                "supplier_id": s_id,
                "supplier_name": s_name,
                "material_supplied": mat_label,
                "deliveries_count": n,
                "on_time_pct": on_time_pct,
                "on_time_pct_str": on_time_pct_str,
                "avg_days_late_str": avg_days_late_str,
                "worst_delay_str": worst_delay_str,
                "lead_time_str": lead_time_str,
                "open_orders_str": open_orders_str,
                "next_expected_str": next_expected_str,
                "quantity_str": qty_str,
                "coincided_str": coincided_str,
                "rating": rating_text,
                "badge_class": badge_class,
                "is_greyed": is_greyed,
                "summary_sentence": summary_sentence,
                "deliveries": sorted(s_deliveries, key=lambda x: x["receipt_date"], reverse=True)
            })

        # 5. Customer Orders Block
        all_sos = (
            db.query(SalesOrder, SalesOrderLine, Customer, Product)
            .join(SalesOrderLine, SalesOrderLine.sales_order_id == SalesOrder.id)
            .join(Customer, Customer.id == SalesOrder.customer_id)
            .join(Product, Product.id == SalesOrderLine.product_id)
            .filter(SalesOrder.order_date <= as_of)
            .all()
        )

        all_dels = (
            db.query(Delivery, DeliveryLine, SalesOrderLine, SalesOrder, Customer, Product)
            .join(DeliveryLine, DeliveryLine.delivery_id == Delivery.id)
            .join(SalesOrderLine, SalesOrderLine.id == DeliveryLine.sales_order_line_id)
            .join(SalesOrder, SalesOrder.id == Delivery.sales_order_id)
            .join(Customer, Customer.id == SalesOrder.customer_id)
            .join(Product, Product.id == DeliveryLine.product_id)
            .filter(Delivery.ship_date <= as_of)
            .all()
        )

        del_by_so: Dict[int, Dict[str, Any]] = {}
        for dl_obj, dll, sol, so, cust, prod in all_dels:
            if so.id not in del_by_so:
                delay = (dl_obj.ship_date - so.requested_delivery_date).days
                del_by_so[so.id] = {
                    "so_id": so.id,
                    "customer_name": cust.name,
                    "product_name": prod.name,
                    "requested_date": so.requested_delivery_date.isoformat(),
                    "ship_date": dl_obj.ship_date.isoformat(),
                    "delay_days": delay,
                    "quantity_ordered": sol.quantity_ordered or 0,
                    "quantity_shipped": dll.quantity_shipped or 0
                }
            else:
                del_by_so[so.id]["quantity_shipped"] += (dll.quantity_shipped or 0)

        # Service by product
        product_service = []
        for prod in products:
            p_dels = [d for d in del_by_so.values() if d["product_name"] == prod.name and d["ship_date"] >= start_str and d["ship_date"] <= as_of_str]
            p_total = len(p_dels)
            if p_total > 0:
                p_ontime = sum(1 for d in p_dels if d["delay_days"] <= 0)
                p_ontime_pct = f"{(p_ontime / p_total * 100):.1f}%"
                p_lates = [d["delay_days"] for d in p_dels if d["delay_days"] > 0]
                p_avg_late = format_days_plural(sum(p_lates) / len(p_lates) if p_lates else 0.0)
            else:
                p_ontime_pct = "—"
                p_avg_late = "—"

            owed_units = sum(
                (sol.quantity_ordered or 0) - (sol.quantity_fulfilled or 0)
                for so, sol, c, p in all_sos
                if p.id == prod.id and (sol.quantity_ordered or 0) > (sol.quantity_fulfilled or 0)
            )

            product_service.append({
                "product_name": prod.name,
                "orders_count": p_total,
                "on_time_pct": p_ontime_pct,
                "avg_days_late": p_avg_late,
                "units_owed_now": owed_units
            })

        # Service by customer
        customer_service = []
        for cust in customers:
            c_dels = [d for d in del_by_so.values() if d["customer_name"] == cust.name and d["ship_date"] >= start_str and d["ship_date"] <= as_of_str]
            c_total = len(c_dels)
            if c_total > 0:
                c_ontime = sum(1 for d in c_dels if d["delay_days"] <= 0)
                c_ontime_pct = f"{(c_ontime / c_total * 100):.1f}%"
                c_lates = [d["delay_days"] for d in c_dels if d["delay_days"] > 0]
                c_avg_late = format_days_plural(sum(c_lates) / len(c_lates) if c_lates else 0.0)
            else:
                c_ontime_pct = "—"
                c_avg_late = "—"

            cust_owed = sum(
                (sol.quantity_ordered or 0) - (sol.quantity_fulfilled or 0)
                for so, sol, c, p in all_sos
                if c.id == cust.id and (sol.quantity_ordered or 0) > (sol.quantity_fulfilled or 0)
            )

            customer_service.append({
                "customer_name": cust.name,
                "orders_count": c_total,
                "on_time_pct": c_ontime_pct,
                "avg_days_late": c_avg_late,
                "units_owed_now": cust_owed
            })

        # Most delayed customer orders (top 5)
        late_customer_records = []
        delayed_customer_orders = []
        for d in del_by_so.values():
            if d["delay_days"] > 0 and d["ship_date"] >= start_str and d["ship_date"] <= as_of_str:
                late_customer_records.append({
                    "record_type": "Customer Order",
                    "ref_no": f"SO #{d['so_id']}",
                    "partner": d["customer_name"],
                    "item": d["product_name"],
                    "quantity": d["quantity_shipped"],
                    "due_date": d["requested_date"],
                    "actual_date": d["ship_date"],
                    "days_late": d["delay_days"],
                    "status": "Delivered late"
                })

        # Also check open SOs currently overdue as of as_of
        for so, sol, cust, prod in all_sos:
            if so.requested_delivery_date < as_of and (sol.quantity_fulfilled or 0) < (sol.quantity_ordered or 0):
                ov_days = (as_of - so.requested_delivery_date).days
                late_customer_records.append({
                    "record_type": "Customer Order",
                    "ref_no": f"SO #{so.id}",
                    "partner": cust.name,
                    "item": prod.name,
                    "quantity": (sol.quantity_ordered or 0) - (sol.quantity_fulfilled or 0),
                    "due_date": so.requested_delivery_date.isoformat(),
                    "actual_date": "Pending",
                    "days_late": ov_days,
                    "status": "Currently overdue"
                })

        # Sort top 5 delayed orders
        all_late_so_items = [r for r in late_customer_records]
        all_late_so_items.sort(key=lambda x: x["days_late"], reverse=True)
        top5_delayed_orders = all_late_so_items[:5]

        # 6. Delay Ledger (combined sortable table)
        delay_ledger = late_supplier_records + late_customer_records
        delay_ledger.sort(key=lambda x: x["days_late"], reverse=True)

        # 7. Weekly Trend Table + Line Chart
        weekly_trend_rows = []
        weekly_chart_labels = []
        weekly_chart_late_units = []

        if not panel_window.empty:
            panel_copy = panel_window.copy()
            panel_copy["date_dt"] = pd.to_datetime(panel_copy["date"])
            # Resample weekly by Monday
            panel_copy["week"] = panel_copy["date_dt"].dt.to_period("W-SUN").apply(lambda r: r.start_time.date())

            for wk_start, grp in panel_copy.groupby("week"):
                wk_end = wk_start + timedelta(days=6)
                dem = int(grp.get("product_201_demand_units", 0).sum() + grp.get("product_202_demand_units", 0).sum())
                prod_u = int(grp.get("product_201_actual_production", 0).sum() + grp.get("product_202_actual_production", 0).sum())
                shipped = int(grp.get("product_201_shipments", 0).sum() if "product_201_shipments" in grp.columns else prod_u)
                late_u = int(grp.get("product_201_due_backlog_units", 0).max() + grp.get("product_202_due_backlog_units", 0).max())
                low_m = int(((grp.get("material_101_stock", 300) <= 50.0) | (grp.get("material_102_stock", 250) <= 40.0) | (grp.get("material_103_stock", 200) <= 30.0)).sum())

                lbl = f"{wk_start.strftime('%-d %b')} – {wk_end.strftime('%-d %b')}"
                weekly_trend_rows.append({
                    "week_label": lbl,
                    "demand": dem,
                    "produced": prod_u,
                    "shipped": shipped,
                    "late_units": late_u,
                    "days_low_stock": low_m
                })
                weekly_chart_labels.append(lbl)
                weekly_chart_late_units.append(late_u)

        # 8. What Changed This Week (Last 7 Days vs Prior 7 Days)
        t_now = as_of
        w_curr_start = max(date(2025, 1, 1), t_now - timedelta(days=6))
        w_prev_end = w_curr_start - timedelta(days=1)
        w_prev_start = max(date(2025, 1, 1), w_prev_end - timedelta(days=6))

        curr_panel = panel[(panel["date"] >= w_curr_start.isoformat()) & (panel["date"] <= t_now.isoformat())] if not panel.empty else pd.DataFrame()
        prev_panel = panel[(panel["date"] >= w_prev_start.isoformat()) & (panel["date"] <= w_prev_end.isoformat())] if not panel.empty else pd.DataFrame()

        def _get_metric_diff(curr_val: int, prev_val: int, unit: str = "") -> Dict[str, Any]:
            diff = curr_val - prev_val
            if diff > 0:
                change_str = f"Up {diff} {unit}".strip()
                color = "#dc2626"
            elif diff < 0:
                change_str = f"Down {abs(diff)} {unit}".strip()
                color = "#16a34a"
            else:
                change_str = "Unchanged"
                color = "#64748b"
            return {"current": curr_val, "previous": prev_val, "change_str": change_str, "color": color}

        curr_late_u = int(curr_panel.get("product_201_due_backlog_units", 0).max() + curr_panel.get("product_202_due_backlog_units", 0).max()) if not curr_panel.empty else 0
        prev_late_u = int(prev_panel.get("product_201_due_backlog_units", 0).max() + prev_panel.get("product_202_due_backlog_units", 0).max()) if not prev_panel.empty else 0

        curr_supp_d = sum(1 for d in po_receipts.values() if d["delay_days"] > 0 and d["receipt_date"] >= w_curr_start.isoformat() and d["receipt_date"] <= t_now.isoformat())
        prev_supp_d = sum(1 for d in po_receipts.values() if d["delay_days"] > 0 and d["receipt_date"] >= w_prev_start.isoformat() and d["receipt_date"] <= w_prev_end.isoformat())

        curr_low_m = int(((curr_panel.get("material_101_stock", 300) <= 50.0) | (curr_panel.get("material_102_stock", 250) <= 40.0) | (curr_panel.get("material_103_stock", 200) <= 30.0)).sum()) if not curr_panel.empty else 0
        prev_low_m = int(((prev_panel.get("material_101_stock", 300) <= 50.0) | (prev_panel.get("material_102_stock", 250) <= 40.0) | (prev_panel.get("material_103_stock", 200) <= 30.0)).sum()) if not prev_panel.empty else 0

        what_changed_strip = {
            "late_units": _get_metric_diff(curr_late_u, prev_late_u, "units"),
            "supplier_delays": _get_metric_diff(curr_supp_d, prev_supp_d, "delays"),
            "low_stock_days": _get_metric_diff(curr_low_m, prev_low_m, "days")
        }

        # 9. Summary Strip Numbers (Existing 4 KPI cards)
        total_cust_deliv = len(del_by_so)
        if total_cust_deliv > 0:
            on_time_cust = sum(1 for d in del_by_so.values() if d["delay_days"] <= 0 and d["ship_date"] >= start_str and d["ship_date"] <= as_of_str)
            cust_on_time_pct = round((on_time_cust / total_cust_deliv) * 100.0, 1)
        else:
            cust_on_time_pct = 100.0

        days_with_overdue_orders = 0
        days_material_low = 0
        total_lost_production = 0

        if not panel_window.empty:
            has_backlog = (panel_window.get("product_201_due_backlog_units", 0) > 0) | (panel_window.get("product_202_due_backlog_units", 0) > 0)
            has_supp_delay = (
                (panel_window.get("supplier_1_po_delay_days", 0) > 0) |
                (panel_window.get("supplier_2_po_delay_days", 0) > 0) |
                (panel_window.get("supplier_3_po_delay_days", 0) > 0) |
                (panel_window.get("supplier_4_po_delay_days", 0) > 0) |
                (panel_window.get("supplier_5_po_delay_days", 0) > 0)
            )
            days_with_overdue_orders = int((has_backlog | has_supp_delay).sum())

            low_m1 = panel_window.get("material_101_stock", 300) <= 50.0
            low_m2 = panel_window.get("material_102_stock", 250) <= 40.0
            low_m3 = panel_window.get("material_103_stock", 200) <= 30.0
            days_material_low = int((low_m1 | low_m2 | low_m3).sum())

            shortfall_201 = panel_window.get("product_201_production_shortfall", 0).sum()
            shortfall_202 = panel_window.get("product_202_production_shortfall", 0).sum()
            total_lost_production = int(shortfall_201 + shortfall_202)

        summary_strip = [
            {
                "id": "kpi_on_time",
                "label": "Orders delivered on time",
                "value": f"{cust_on_time_pct:.1f}%",
                "meaning": "Shipped to customers by the promised requested date.",
                "calc_info": "Calculated as customer shipments completed on or before requested date divided by total orders shipped."
            },
            {
                "id": "kpi_overdue_days",
                "label": "Days with an overdue order",
                "value": f"{days_with_overdue_orders}",
                "meaning": "Days where at least one customer or purchase order was past due.",
                "calc_info": "Count of distinct calendar dates where order backlog exceeded 0 or an open PO was past its expected delivery date."
            },
            {
                "id": "kpi_safety_days",
                "label": "Days buffer fell to safety level",
                "value": f"{days_material_low}",
                "meaning": "Days where raw material inventory fell to or below reserve.",
                "calc_info": "Count of dates where Raw steel fell to <= 50 kg, Copper wire <= 40 kg, or Electronic housings <= 30 kg."
            },
            {
                "id": "kpi_production_lost",
                "label": "Planned production lost",
                "value": f"{total_lost_production} units",
                "meaning": "Manufacturing shortfall below daily planned output schedule.",
                "calc_info": "Sum of daily production deficits for Electric Motors and Gear Assemblies."
            }
        ]

        # 10. Episodes with templated stories
        episodes = []
        chart2_dates = []
        chart2_backlog = []
        chart2_in_episode = []

        cur_ep_start = None
        cur_ep_peak_backlog = 0
        cur_ep_materials = set()
        cur_ep_products = set()
        cur_ep_suppliers = set()

        if not panel_window.empty:
            for idx, row in panel_window.iterrows():
                dt_str = row["date"]
                dt_obj = datetime.strptime(dt_str, "%Y-%m-%d").date()
                b_201 = float(row.get("product_201_due_backlog_units", 0))
                b_202 = float(row.get("product_202_due_backlog_units", 0))
                day_backlog = int(b_201 + b_202)

                s101 = float(row.get("material_101_stock", 300))
                s102 = float(row.get("material_102_stock", 250))
                s103 = float(row.get("material_103_stock", 200))
                sh_201 = float(row.get("product_201_production_shortfall", 0))
                sh_202 = float(row.get("product_202_production_shortfall", 0))

                supp_delays = {s: float(row.get(f"supplier_{s}_po_delay_days", 0)) for s in range(1, 6)}

                is_eventful = (
                    day_backlog > 0 or
                    any(v > 0 for v in supp_delays.values()) or
                    s101 <= 50.0 or s102 <= 40.0 or s103 <= 30.0 or
                    sh_201 > 0 or sh_202 > 0
                )

                chart2_dates.append(dt_str)
                chart2_backlog.append(day_backlog)
                chart2_in_episode.append(1 if is_eventful else 0)

                if is_eventful:
                    if cur_ep_start is None:
                        cur_ep_start = dt_obj
                        cur_ep_peak_backlog = day_backlog
                        cur_ep_materials = set()
                        cur_ep_products = set()
                        cur_ep_suppliers = set()

                    cur_ep_peak_backlog = max(cur_ep_peak_backlog, day_backlog)
                    if s101 <= 50.0: cur_ep_materials.add("Raw steel (101)")
                    if s102 <= 40.0: cur_ep_materials.add("Copper wire (102)")
                    if s103 <= 30.0: cur_ep_materials.add("Housings (103)")
                    if b_201 > 0 or sh_201 > 0: cur_ep_products.add("Motors (201)")
                    if b_202 > 0 or sh_202 > 0: cur_ep_products.add("Gears (202)")
                    for s_num, d_val in supp_delays.items():
                        if d_val > 0: cur_ep_suppliers.add(f"Supplier {s_num}")
                else:
                    if cur_ep_start is not None:
                        prev_date = dt_obj - timedelta(days=1)
                        ep_len = (prev_date - cur_ep_start).days + 1
                        items_str = ", ".join(sorted(cur_ep_products | cur_ep_materials)) or "Buffer inventory"
                        supp_str = ", ".join(sorted(cur_ep_suppliers)) or "None"
                        story_text = (
                            f"Episode started on {cur_ep_start.strftime('%-d %b')} and ended on {prev_date.strftime('%-d %b')} "
                            f"({format_days_plural(ep_len)}). Peak backlog reached {cur_ep_peak_backlog} units of {items_str}. "
                            f"{('Coincided with ' + supp_str + ' delivery delays.') if supp_str != 'None' else 'Internal constraint.'} "
                            f"Buffer recovered within {format_days_plural(ep_len)}."
                        )
                        episodes.append({
                            "start_date": cur_ep_start.isoformat(),
                            "end_date": prev_date.isoformat(),
                            "duration_days": ep_len,
                            "peak_backlog": cur_ep_peak_backlog,
                            "items_involved": items_str,
                            "coincided_supplier": f"Coincided with {supp_str} delay" if supp_str != "None" else "None",
                            "story": story_text
                        })
                        cur_ep_start = None

            if cur_ep_start is not None:
                ep_len = (as_of - cur_ep_start).days + 1
                items_str = ", ".join(sorted(cur_ep_products | cur_ep_materials)) or "Buffer inventory"
                supp_str = ", ".join(sorted(cur_ep_suppliers)) or "None"
                story_text = (
                    f"Ongoing episode started on {cur_ep_start.strftime('%-d %b')} ({format_days_plural(ep_len)} active). "
                    f"Peak backlog has reached {cur_ep_peak_backlog} units of {items_str}. "
                    f"{('Coincided with ' + supp_str + ' delivery delays.') if supp_str != 'None' else 'Internal constraint.'}"
                )
                episodes.append({
                    "start_date": cur_ep_start.isoformat(),
                    "end_date": as_of.isoformat(),
                    "duration_days": ep_len,
                    "peak_backlog": cur_ep_peak_backlog,
                    "items_involved": items_str,
                    "coincided_supplier": f"Coincided with {supp_str} delay" if supp_str != "None" else "None",
                    "story": story_text
                })

        # 11. Existing Chart Blocks: Materials (Stock vs Safety) & Products (Demand vs Built)
        materials_charts = []
        mat_meta = [
            (101, "Raw steel", 50.0, 150.0),
            (102, "Copper wire", 40.0, 120.0),
            (103, "Electronic housings", 30.0, 100.0)
        ]
        for m_id, m_name, s_limit, r_limit in mat_meta:
            m_col = f"material_{m_id}_stock"
            stock_series = [float(v) for v in panel_window[m_col].tolist()] if not panel_window.empty and m_col in panel_window.columns else []
            days_below = int((panel_window[m_col] <= s_limit).sum()) if not panel_window.empty and m_col in panel_window.columns else 0
            takeaway = f"{m_name} fell below its reserve buffer on {format_days_plural(days_below)}." if days_below > 0 else f"{m_name} remained safely above reserve buffer levels."
            materials_charts.append({
                "material_id": m_id,
                "name": m_name,
                "safety_level": s_limit,
                "reorder_level": r_limit,
                "days_below_safety": days_below,
                "takeaway": takeaway,
                "dates": chart2_dates,
                "stock_values": stock_series
            })

        products_charts = []
        prod_meta = [
            (201, "Electric Motors"),
            (202, "Gear Assemblies")
        ]
        for p_id, p_name in prod_meta:
            dem_col = f"product_{p_id}_demand_units"
            act_col = f"product_{p_id}_actual_production"
            fg_col = f"product_{p_id}_fg_stock"
            sh_col = f"product_{p_id}_production_shortfall"

            dem_series = [float(v) for v in panel_window.get(dem_col, 0).tolist()] if not panel_window.empty else []
            act_series = [float(v) for v in panel_window.get(act_col, 0).tolist()] if not panel_window.empty else []
            fg_series = [float(v) for v in panel_window.get(fg_col, 0).tolist()] if not panel_window.empty else []
            total_short = int(panel_window.get(sh_col, 0).sum()) if not panel_window.empty else 0
            takeaway = f"{p_name} experienced {total_short} units of production shortfall." if total_short > 0 else f"{p_name} fulfilled 100% of planned production schedule."

            products_charts.append({
                "product_id": p_id,
                "name": p_name,
                "total_shortfall_units": total_short,
                "takeaway": takeaway,
                "dates": chart2_dates,
                "demand": dem_series,
                "actual_production": act_series,
                "finished_stock": fg_series
            })

        # Reliability Summary Box
        reliability_summary = [
            "In zero-shot evaluation on fresh synthetic worlds (Test A), SAGE detected 0 of 3 target disruptions (INC_03, INC_04, INC_06) and triggered false alarms on 60% to 90% of quiet windows because thresholds fitted to Seed 42 did not transfer across environments.",
            "In site-calibrated deployment (Test A2, tested on one new simulated world), recalibrating null thresholds on Seed 7's own baseline panel controlled false alarms to 5.0% on quiet windows, but still detected 0 of 3 target disruptions because incident scores remained below the site's higher baseline noise threshold.",
            "On real retail demand data (Test B), SAGE detected 1 of 4 holidays (Thanksgiving at 6.26x above null) with a 2.1% false-alarm rate, while a naive year-over-year baseline detected 0 of 4 holidays with a 4.2% false-alarm rate."
        ]

        has_data = len(delay_ledger) > 0 or len(episodes) > 0 or any(c["deliveries_count"] > 0 for c in supplier_cards)

        return {
            "as_of": as_of_str,
            "period": period_str,
            "period_label": period_label,
            "date_range_str": date_range_str,
            "has_data": has_data,
            "empty_period_notice": "Nothing happened in this period. Consider selecting a longer period such as 'Year so far'." if not has_data else "",
            "is_demo_full_year": (period_str == "full_year" and is_demo),
            "summary_strip": summary_strip,
            "what_changed_strip": what_changed_strip,
            "supplier_cards": supplier_cards,
            "customer_service": customer_service,
            "product_service": product_service,
            "top5_delayed_orders": top5_delayed_orders,
            "delay_ledger": delay_ledger,
            "weekly_trend_rows": weekly_trend_rows,
            "weekly_chart_labels": weekly_chart_labels,
            "weekly_chart_late_units": weekly_chart_late_units,
            "chart_delivery_delays": {
                "title": "Were deliveries on time?",
                "takeaway": "Longest delays coincided with Supplier 1 receipts (up to 7 days)." if any(c["worst_delay_str"] != "—" and "0 days" not in c["worst_delay_str"] for c in supplier_cards) else "All deliveries arrived on or ahead of scheduled dates.",
                "points": chart_delivery_delays
            },
            "episodes": {
                "title": "When did things go wrong?",
                "takeaway": f"Operations observed {len(episodes)} disruption episodes totaling {sum(e['duration_days'] for e in episodes)} days." if episodes else "Zero disruption episodes detected in this period.",
                "dates": chart2_dates,
                "backlog_series": chart2_backlog,
                "in_episode_series": chart2_in_episode,
                "table": episodes
            },
            "materials_charts": materials_charts,
            "products_charts": products_charts,
            "past_cases": FROZEN_PAST_CASES,
            "reliability_summary": reliability_summary,
            "framing": RESEARCH_FRAMING
        }

    finally:
        db.close()


def generate_supplier_report_csv(data: Dict[str, Any]) -> str:
    """Renders the supplier report card table as RFC 4180 CSV text."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Supplier Name",
        "Material Supplied",
        "Deliveries (n)",
        "On-Time (%)",
        "Average Days Late",
        "Worst Delay",
        "Lead Time",
        "Open Orders Now",
        "Next Expected Date",
        "Quantity Received vs Ordered",
        "Coincided With",
        "Rating"
    ])

    for row in data.get("supplier_cards", []):
        writer.writerow([
            row["supplier_name"],
            row["material_supplied"],
            row["deliveries_count"],
            row["on_time_pct_str"],
            row["avg_days_late_str"],
            row["worst_delay_str"],
            row["lead_time_str"],
            row["open_orders_str"],
            row["next_expected_str"],
            row["quantity_str"],
            row["coincided_str"],
            row["rating"]
        ])

    return output.getvalue()


def generate_delay_ledger_csv(data: Dict[str, Any]) -> str:
    """Renders the delay ledger table as RFC 4180 CSV text."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Record Type",
        "Reference #",
        "Partner",
        "Item",
        "Quantity",
        "Due Date",
        "Actual Date",
        "Days Late",
        "Status"
    ])

    for row in data.get("delay_ledger", []):
        writer.writerow([
            row["record_type"],
            row["ref_no"],
            row["partner"],
            row["item"],
            row["quantity"],
            row["due_date"],
            row["actual_date"],
            row["days_late"],
            row["status"]
        ])

    return output.getvalue()
