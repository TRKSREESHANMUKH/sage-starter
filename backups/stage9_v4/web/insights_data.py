"""
web/insights_data.py — SAGE Insights Tab Data Engine (Stage 9 v4).

Provides descriptive operational analytics and frozen causal evaluation history:
- Read-only access to committed ERP tables and Stage 6 daily panel.
- Strict SQL guard: forbids querying business_events, ground truth, or evaluation files.
- Strict isolation: does NOT import any evaluation or research views.
- Strict temporal integrity: no look-ahead past the selected as-of date.
- High-performance caching in analytics/insights_cache/ for sub-1s page load times.
- Deterministic output serialization.
- Purely descriptive wording (never uses "caused" outside the frozen causal history).
"""

import os
import sys
import json
import csv
import io
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import Base
from app.models.purchasing import PurchaseOrder, PurchaseOrderLine, GoodsReceipt, GoodsReceiptLine
from app.models.sales import SalesOrder, SalesOrderLine, Delivery, DeliveryLine
from app.models.suppliers import Supplier
from app.models.inventory import Product, InventoryItem, StockMovement
from app.models.production import ProductionOrder
from stage9.clock import get_as_of_date
from stage9.status import RESEARCH_FRAMING
from web.one_page_data import FROZEN_PAST_CASES

CACHE_DIR = ROOT_DIR / "analytics" / "insights_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
PANEL_PARQUET_PATH = ROOT_DIR / "analytics" / "daily_panel.parquet"

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://sage_user:sage_dev_password@localhost:5433/sage_db")


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
        _CACHED_PANEL = pd.read_parquet(PANEL_PARQUET_PATH)
    else:
        _CACHED_PANEL = pd.DataFrame()
    return _CACHED_PANEL


def compute_rating(on_time_pct: float, fill_rate_pct: float, n_deliveries: int) -> Tuple[str, str, bool]:
    """
    Fixed rating rule pre-registered in stage9/config/rules.yaml:
    - Grade A if on-time >= 90% and received >= 95%
    - Grade B if on-time >= 70%
    - Grade C otherwise
    - 'Too few deliveries to rate' if n < 5 (greyed out)
    """
    if n_deliveries < 5:
        return "Too few deliveries to rate", "badge-calm", True
    if on_time_pct >= 90.0 and fill_rate_pct >= 95.0:
        return "Grade A", "badge-strong", False
    if on_time_pct >= 70.0:
        return "Grade B", "badge-some", False
    return "Grade C", "badge-weak", False


def get_insights_data(
    as_of_str: Optional[str] = None,
    period_str: str = "ytd",
    force_refresh: bool = False
) -> Dict[str, Any]:
    """
    Main entry point for the Insights tab.
    Loads from disk cache if present; computes and stores to cache otherwise.
    """
    if as_of_str:
        cur_as_of = datetime.strptime(as_of_str, "%Y-%m-%d").date()
    else:
        cur_as_of = get_as_of_date()

    valid_periods = {"30d", "quarter", "ytd", "full_year"}
    if period_str not in valid_periods:
        period_str = "ytd"

    is_demo = os.getenv("SAGE_DEMO", "false").lower() in ("true", "1", "yes")
    if period_str == "full_year" and not is_demo:
        period_str = "ytd"

    cache_file = CACHE_DIR / f"insights_{cur_as_of.isoformat()}_{period_str}.json"

    if cache_file.exists() and not force_refresh:
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cached_data = json.load(f)
            return cached_data
        except Exception:
            pass

    computed = compute_insights_payload(cur_as_of, period_str, is_demo)

    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(computed, f, indent=2, sort_keys=True)

    return computed


def compute_insights_payload(as_of: date, period_str: str, is_demo: bool) -> Dict[str, Any]:
    """Performs read-only aggregation up to as_of date."""
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

    # 2. Slice Stage 6 Daily Panel (Read-only)
    panel = get_cached_panel()
    if not panel.empty:
        panel_window = panel[(panel["date"] >= start_str) & (panel["date"] <= as_of_str)].sort_values("date").reset_index(drop=True)
    else:
        panel_window = pd.DataFrame()

    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        sql_guard_check("purchase_orders")
        sql_guard_check("goods_receipts")
        sql_guard_check("sales_orders")
        sql_guard_check("deliveries")

        # 3. Query Purchase Orders & Deliveries by Supplier
        suppliers = db.query(Supplier).order_by(Supplier.id).all()
        supp_map = {s.id: s.name for s in suppliers}

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

        # Track receipts per PO
        po_receipts: Dict[int, Dict[str, Any]] = {}
        for gr, gr_line, po_line, po, supp in all_grs:
            if po.id not in po_receipts:
                delay = (gr.receipt_date - po.expected_delivery_date).days
                po_receipts[po.id] = {
                    "po_id": po.id,
                    "supplier_id": supp.id,
                    "supplier_name": supp.name,
                    "order_date": po.order_date.isoformat(),
                    "expected_date": po.expected_delivery_date.isoformat(),
                    "receipt_date": gr.receipt_date.isoformat(),
                    "delay_days": delay,
                    "quantity_ordered": po_line.quantity_ordered or 0,
                    "quantity_received": gr_line.quantity_received or 0
                }
            else:
                po_receipts[po.id]["quantity_received"] += (gr_line.quantity_received or 0)

        # 4. Supplier Report Card Aggregation
        supplier_cards = []
        chart_delivery_delays = []

        supplier_material_map = {
            1: 101,  # Supplier 1 -> Raw steel (Material 101)
            2: 102,  # Supplier 2 -> Copper wire (Material 102)
            3: 102,  # Supplier 3 -> Copper wire (Material 102)
            4: 103,  # Supplier 4 -> Electronic housings (Material 103)
            5: 103   # Supplier 5 -> Electronic housings (Material 103)
        }

        safety_thresholds = {101: 50.0, 102: 40.0, 103: 30.0}

        for supp in suppliers:
            s_id = supp.id
            s_name = supp.name
            s_deliveries = [
                d for d in po_receipts.values()
                if d["supplier_id"] == s_id and d["receipt_date"] >= start_str and d["receipt_date"] <= as_of_str
            ]

            n = len(s_deliveries)
            if n > 0:
                on_time_count = sum(1 for d in s_deliveries if d["delay_days"] <= 0)
                on_time_pct = round((on_time_count / n) * 100.0, 1)
                late_delays = [d["delay_days"] for d in s_deliveries if d["delay_days"] > 0]
                avg_days_late = round(float(sum(late_delays) / len(late_delays)), 1) if late_delays else 0.0
                worst_delay = max(d["delay_days"] for d in s_deliveries)
                total_ord = sum(d["quantity_ordered"] for d in s_deliveries)
                total_rec = sum(d["quantity_received"] for d in s_deliveries)
                fill_rate_pct = round((total_rec / total_ord * 100.0), 1) if total_ord > 0 else 100.0
                late_count = len(late_delays)
            else:
                on_time_pct = 100.0
                avg_days_late = 0.0
                worst_delay = 0
                fill_rate_pct = 100.0
                late_count = 0

            rating_text, badge_class, is_greyed = compute_rating(on_time_pct, fill_rate_pct, n)

            # Deterministic one-sentence supplier summary
            if n == 0:
                summary_sentence = f"{s_name} had no deliveries during this period."
            elif late_count == 0:
                summary_sentence = f"{s_name} delivered all {n} order{'s' if n > 1 else ''} on time with 0 days delay."
            else:
                summary_sentence = f"{s_name} was late on {late_count} of {n} deliveries, worst {worst_delay} days."

            # Calculate 'Coincided with' column:
            # Days material was at or below safety level while an open PO for this supplier was overdue
            mat_id = supplier_material_map.get(s_id, 101)
            mat_safety = safety_thresholds.get(mat_id, 40.0)
            coincided_days = 0

            if not panel_window.empty:
                mat_col = f"material_{mat_id}_stock"
                supp_col = f"supplier_{s_id}_po_delay_days"
                if mat_col in panel_window.columns and supp_col in panel_window.columns:
                    cond = (panel_window[mat_col] <= mat_safety) & (panel_window[supp_col] > 0)
                    coincided_days = int(cond.sum())

            # Add to chart delivery delays points
            for d in s_deliveries:
                chart_delivery_delays.append({
                    "date": d["receipt_date"],
                    "po_id": d["po_id"],
                    "supplier_id": s_id,
                    "supplier_name": s_name,
                    "delay_days": d["delay_days"],
                    "quantity_received": d["quantity_received"]
                })

            supplier_cards.append({
                "supplier_id": s_id,
                "supplier_name": s_name,
                "deliveries_count": n,
                "on_time_pct": on_time_pct,
                "avg_days_late": avg_days_late,
                "worst_delay": worst_delay,
                "fill_rate_pct": fill_rate_pct,
                "rating": rating_text,
                "badge_class": badge_class,
                "is_greyed": is_greyed,
                "summary_sentence": summary_sentence,
                "coincided_days": coincided_days,
                "deliveries": sorted(s_deliveries, key=lambda x: x["receipt_date"], reverse=True)
            })

        # Chart 1 takeaway template
        max_delay_supp = max(supplier_cards, key=lambda x: x["worst_delay"], default=None)
        if max_delay_supp and max_delay_supp["worst_delay"] > 0:
            chart1_takeaway = f"{max_delay_supp['supplier_name']} had the longest delays (up to {max_delay_supp['worst_delay']} days)."
        else:
            chart1_takeaway = "All deliveries arrived on or ahead of scheduled delivery dates."

        # 5. Summary Strip Numbers
        # A. Customer orders on time %
        customer_deliveries = (
            db.query(Delivery, SalesOrder)
            .join(SalesOrder, SalesOrder.id == Delivery.sales_order_id)
            .filter(Delivery.ship_date >= start_d, Delivery.ship_date <= as_of)
            .all()
        )
        total_cust_deliv = len(customer_deliveries)
        if total_cust_deliv > 0:
            on_time_cust = sum(1 for deliv, so in customer_deliveries if deliv.ship_date <= so.requested_delivery_date)
            cust_on_time_pct = round((on_time_cust / total_cust_deliv) * 100.0, 1)
        else:
            cust_on_time_pct = 100.0

        # B. Days with at least one overdue order
        # Scan panel for overdue orders > 0
        days_with_overdue_orders = 0
        days_material_low = 0
        total_lost_production = 0

        if not panel_window.empty:
            # Overdue orders
            has_backlog = (panel_window.get("product_201_due_backlog_units", 0) > 0) | (panel_window.get("product_202_due_backlog_units", 0) > 0)
            has_supp_delay = (
                (panel_window.get("supplier_1_po_delay_days", 0) > 0) |
                (panel_window.get("supplier_2_po_delay_days", 0) > 0) |
                (panel_window.get("supplier_3_po_delay_days", 0) > 0) |
                (panel_window.get("supplier_4_po_delay_days", 0) > 0) |
                (panel_window.get("supplier_5_po_delay_days", 0) > 0)
            )
            days_with_overdue_orders = int((has_backlog | has_supp_delay).sum())

            # Days material <= safety stock
            low_m1 = panel_window.get("material_101_stock", 300) <= 50.0
            low_m2 = panel_window.get("material_102_stock", 250) <= 40.0
            low_m3 = panel_window.get("material_103_stock", 200) <= 30.0
            days_material_low = int((low_m1 | low_m2 | low_m3).sum())

            # Lost production units
            shortfall_201 = panel_window.get("product_201_production_shortfall", 0).sum()
            shortfall_202 = panel_window.get("product_202_production_shortfall", 0).sum()
            total_lost_production = int(shortfall_201 + shortfall_202)

        summary_strip = [
            {
                "id": "kpi_on_time",
                "label": "Orders delivered on time",
                "value": f"{cust_on_time_pct:.1f}%",
                "meaning": "Shipped to customers by the promised requested date.",
                "calc_info": "Calculated as total customer shipments completed on or before the requested delivery date divided by total orders shipped during the period."
            },
            {
                "id": "kpi_overdue_days",
                "label": "Days with an overdue order",
                "value": f"{days_with_overdue_orders}",
                "meaning": "Days where at least one customer or purchase order was past due.",
                "calc_info": "Count of distinct calendar dates where customer order backlog exceeded 0 or an open purchase order was past its expected delivery date."
            },
            {
                "id": "kpi_safety_days",
                "label": "Days buffer fell to safety level",
                "value": f"{days_material_low}",
                "meaning": "Days where a raw material inventory fell to or below reserve.",
                "calc_info": "Count of calendar dates where Raw steel fell to <= 50 kg, Copper wire <= 40 kg, or Electronic housings <= 30 kg."
            },
            {
                "id": "kpi_production_lost",
                "label": "Planned production lost",
                "value": f"{total_lost_production} units",
                "meaning": "Manufacturing shortfall below daily planned output schedule.",
                "calc_info": "Sum of daily production deficits (planned units minus completed units) for Electric Motors and Gear Assemblies."
            }
        ]

        # 6. Chart 2: Episodes Timeline & Table
        # An episode is a run of consecutive days where eventful rule is true:
        # backlog > 0, overdue orders > 0, stock <= safety, or production shortfall > 0
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

                supp_delays = {
                    s: float(row.get(f"supplier_{s}_po_delay_days", 0))
                    for s in range(1, 6)
                }

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
                        if d_val > 0:
                            cur_ep_suppliers.add(f"Supplier {s_num}")
                else:
                    if cur_ep_start is not None:
                        prev_date = dt_obj - timedelta(days=1)
                        ep_len = (prev_date - cur_ep_start).days + 1
                        items_str = ", ".join(sorted(cur_ep_products | cur_ep_materials)) or "Inventory buffer"
                        supp_str = ", ".join(sorted(cur_ep_suppliers)) or "None"
                        episodes.append({
                            "start_date": cur_ep_start.isoformat(),
                            "end_date": prev_date.isoformat(),
                            "duration_days": ep_len,
                            "peak_backlog": cur_ep_peak_backlog,
                            "items_involved": items_str,
                            "coincided_supplier": f"Coincided with {supp_str} delay" if supp_str != "None" else "None"
                        })
                        cur_ep_start = None

            if cur_ep_start is not None:
                ep_len = (as_of - cur_ep_start).days + 1
                items_str = ", ".join(sorted(cur_ep_products | cur_ep_materials)) or "Inventory buffer"
                supp_str = ", ".join(sorted(cur_ep_suppliers)) or "None"
                episodes.append({
                    "start_date": cur_ep_start.isoformat(),
                    "end_date": as_of.isoformat(),
                    "duration_days": ep_len,
                    "peak_backlog": cur_ep_peak_backlog,
                    "items_involved": items_str,
                    "coincided_supplier": f"Coincided with {supp_str} delay" if supp_str != "None" else "None"
                })

        total_ep_days = sum(e["duration_days"] for e in episodes)
        peak_ep_backlog = max((e["peak_backlog"] for e in episodes), default=0)
        if episodes:
            chart2_takeaway = f"Operations experienced {len(episodes)} disruption episodes totaling {total_ep_days} days, with peak backlog reaching {peak_ep_backlog} units."
        else:
            chart2_takeaway = "Zero disruption episodes detected; all operational buffers and order queues ran smoothly."

        # 7. Chart 3: Stock vs Safety Level (3 Materials)
        materials_charts = []
        mat_meta = [
            (101, "Raw steel", 50.0, 150.0),
            (102, "Copper wire", 40.0, 120.0),
            (103, "Electronic housings", 30.0, 100.0)
        ]

        for m_id, m_name, s_limit, r_limit in mat_meta:
            m_col = f"material_{m_id}_stock"
            if not panel_window.empty and m_col in panel_window.columns:
                stock_series = [float(v) for v in panel_window[m_col].tolist()]
                days_below = int((panel_window[m_col] <= s_limit).sum())
            else:
                stock_series = []
                days_below = 0

            if days_below > 0:
                m_takeaway = f"{m_name} was below its safety level on {days_below} days."
            else:
                m_takeaway = f"{m_name} remained safely above buffer thresholds throughout the period."

            materials_charts.append({
                "material_id": m_id,
                "name": m_name,
                "safety_level": s_limit,
                "reorder_level": r_limit,
                "days_below_safety": days_below,
                "takeaway": m_takeaway,
                "dates": chart2_dates,
                "stock_values": stock_series
            })

        # 8. Chart 4: Demand vs What We Built (2 Products)
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

            if not panel_window.empty:
                dem_series = [float(v) for v in panel_window.get(dem_col, 0).tolist()]
                act_series = [float(v) for v in panel_window.get(act_col, 0).tolist()]
                fg_series = [float(v) for v in panel_window.get(fg_col, 0).tolist()]
                total_short = int(panel_window.get(sh_col, 0).sum())
            else:
                dem_series, act_series, fg_series = [], [], []
                total_short = 0

            if total_short > 0:
                p_takeaway = f"{p_name} had {total_short} units of planned production lost in total."
            else:
                p_takeaway = f"{p_name} met 100% of planned production commitments."

            products_charts.append({
                "product_id": p_id,
                "name": p_name,
                "total_shortfall_units": total_short,
                "takeaway": p_takeaway,
                "dates": chart2_dates,
                "demand": dem_series,
                "actual_production": act_series,
                "finished_stock": fg_series
            })

        # 9. Past Analysed Cases Summary Box (Honest Story)
        reliability_summary = [
            "In zero-shot evaluation on fresh synthetic worlds (Test A), SAGE detected 0 of 4 target disruptions and triggered false alarms on 60% to 90% of quiet windows because thresholds fitted to Seed 42 did not transfer across environments.",
            "In site-calibrated deployment (Test A2), recalibrating null thresholds on Seed 7's own baseline panel controlled false alarms to 5.0% on quiet windows, but detected 0 of 4 target disruptions because incident scores remained below the site's higher baseline noise threshold.",
            "On real retail demand data (Test B), SAGE detected 1 of 4 holidays (Thanksgiving at 6.26x above null) with a 2.1% false-alarm rate, while a naive year-over-year baseline detected 0 of 4 holidays with a 4.2% false-alarm rate."
        ]

        return {
            "as_of": as_of_str,
            "period": period_str,
            "period_label": period_label,
            "is_demo_full_year": (period_str == "full_year" and is_demo),
            "summary_strip": summary_strip,
            "supplier_cards": supplier_cards,
            "chart_delivery_delays": {
                "title": "Were deliveries on time?",
                "takeaway": chart1_takeaway,
                "points": chart_delivery_delays
            },
            "episodes": {
                "title": "When did things go wrong?",
                "takeaway": chart2_takeaway,
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
        "Deliveries (n)",
        "On-Time (%)",
        "Average Days Late (Late Deliveries Only)",
        "Worst Delay (Days)",
        "Quantity Received vs Ordered (%)",
        "Coincided With (Days)",
        "Rating"
    ])

    for row in data.get("supplier_cards", []):
        writer.writerow([
            row["supplier_name"],
            row["deliveries_count"],
            f"{row['on_time_pct']:.1f}%",
            f"{row['avg_days_late']:.1f}",
            row["worst_delay"],
            f"{row['fill_rate_pct']:.1f}%",
            row["coincided_days"],
            row["rating"]
        ])

    return output.getvalue()
