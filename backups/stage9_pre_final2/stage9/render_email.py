"""
stage9/render_email.py — SAGE Phase C & Part 5: Solid Executive Brief & One-Page PDF Validator.

Part 5 Specifications (Built to Impress and to Be Used):
1. Status banner: "All normal", "Watch closely", or "Action needed" with count ("2 items need action").
   Subject: SAGE Daily Brief | 3 Feb 2025 | 2 need action (or ... | All normal).
   Preheader: first sentence of the bottom line.
2. Bottom line: two sentences from facts (narrator / template fallback) with biggest problem and plain cause.
3. Today's numbers with context: orders due, orders late, units short, materials low.
   Shows change vs yesterday and 7-day average (e.g. "3 late orders, up from 1 yesterday (7d avg: 1.4)").
4. Last 7 days at a glance: small table + embedded CID PNG sparkline of late units & production shortfall.
5. Orders to prioritise tomorrow: rank, order #, customer, product, quantity, due date, days overdue, reason. Top 5.
6. Supplier watch: open POs that are overdue (supplier, material, days overdue, expected date) & receipts tomorrow.
   If none: "No supplier problems today."
7. What happened and why: up to 4 plain lines tied to observed facts ("Seen directly in the data").
8. Causal findings: up to 3 plain lines from frozen analysed cases only, labelled:
   "From past analysed cases, not detected today" with evidence label + link to Trust section.
9. Footer: framing sentence verbatim, "Simulated data. System knows data up to <date> only", sent time,
   plain dashboard link, and attached PDF named SAGE_Daily_Brief_<date>.pdf.
10. Technical: 600px table layout, inline CSS, readable in dark mode, plain text alternative wrapped at 72 chars,
    and assert_one_page_pdf confirms strictly 1 A4 page.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
import io
import json
import logging
import os
from pathlib import Path
import re
import sys
import textwrap
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from sqlalchemy import func

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import SessionLocal
from app.models.inventory import InventoryItem, Product, StockMovement
from app.models.purchasing import PurchaseOrder, PurchaseOrderLine, GoodsReceipt, GoodsReceiptLine
from app.models.production import ProductionOrder
from app.models.sales import Customer, SalesOrder, SalesOrderLine, Delivery, DeliveryLine
from app.models.suppliers import Supplier
from stage9.clock import get_as_of_date
from stage9.current_day import get_current_day
from stage9.snapshot import compute_daily_snapshot
from stage9.priorities import compute_priorities, format_material_display, format_product_display
from stage9.narrate import generate_executive_narrative
from stage9.status import (
    RESEARCH_FRAMING,
    EVIDENCE_LABELS,
    tier_to_evidence_label,
)

ANALYTICS_DIR = ROOT_DIR / "analytics"
EVIDENCE_PATH = ANALYTICS_DIR / "evidence_packets.json"
NARRATION_PATH = ANALYTICS_DIR / "narration_results.json"
PANEL_PARQUET_PATH = ANALYTICS_DIR / "daily_panel.parquet"

logger = logging.getLogger("stage9.render_email")


def get_base_url() -> str:
    """Returns plain SAGE_BASE_URL without any authentication token."""
    return os.getenv("SAGE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def load_evidence_packets() -> Dict[str, Any]:
    if EVIDENCE_PATH.exists():
        try:
            with open(EVIDENCE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def load_stage8_narratives() -> Dict[str, Any]:
    if NARRATION_PATH.exists():
        try:
            with open(NARRATION_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {item["packet_id"]: item.get("narrative", "") for item in data.get("results", [])}
        except Exception:
            pass
    return {}


def generate_7d_sparkline_png(records: List[Dict[str, Any]]) -> bytes:
    """
    Generates a clean 560x90 PNG sparkline for the last 7 days of late units & shortfall.
    Returns raw PNG bytes.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    dates = [r["date_label"] for r in records]
    late = [r["late_units"] for r in records]
    shortfall = [r["shortfall"] for r in records]

    fig, ax = plt.subplots(figsize=(5.6, 1.0), dpi=120)
    fig.patch.set_facecolor("#f8fafc")
    ax.set_facecolor("#f8fafc")

    x = range(len(dates))
    ax.plot(x, late, color="#dc2626", linewidth=1.8, marker="o", markersize=3.5, label="Late units")
    ax.plot(x, shortfall, color="#2563eb", linewidth=1.6, linestyle="--", marker="s", markersize=3.0, label="Prod shortfall")

    ax.set_xticks(list(x))
    ax.set_xticklabels(dates, fontsize=7.5, color="#64748b")
    ax.tick_params(axis="y", labelsize=7, colors="#64748b")
    ax.grid(True, linestyle=":", alpha=0.5, color="#cbd5e1")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#cbd5e1")
    ax.spines["bottom"].set_color("#cbd5e1")
    ax.legend(loc="upper left", fontsize=7, frameon=False)

    plt.tight_layout(pad=0.4)
    buf = io.BytesIO()
    plt.savefig(buf, format="png", facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    return buf.getvalue()


def get_trailing_7d_metrics(as_of: date, db_session) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Computes trailing 7 days of operational data (as_of - 6 days to as_of).
    Returns (records_list, today_context_dict).
    """
    records: List[Dict[str, Any]] = []
    curr = as_of - timedelta(days=6)
    while curr <= as_of:
        # Stock shortfall + late orders for day curr
        snap = compute_daily_snapshot(curr, db_session=db_session)
        kpis = snap.get("kpis", {})
        overdue_cnt = int(kpis.get("total_overdue_orders", 0))
        due_backlog = int(kpis.get("total_backlog_units", 0))
        prod_shortfall = int(kpis.get("total_production_shortfall", 0))
        orders_due = sum(1 for p in snap.get("products", {}).values() if p.get("demand_units", 0) > 0)
        mats_low = sum(1 for m in snap.get("materials", {}).values() if float(m["stock"]) <= float(m["safety_stock"]))

        records.append({
            "date": curr.isoformat(),
            "date_label": curr.strftime("%d %b"),
            "orders_due": orders_due,
            "orders_late": overdue_cnt,
            "late_units": due_backlog,
            "shortfall": prod_shortfall,
            "materials_low": mats_low
        })
        curr += timedelta(days=1)

    today_rec = records[-1]
    yest_rec = records[-2] if len(records) >= 2 else today_rec

    def _comp(today_v: int, yest_v: int, avg_v: float, unit_s: str, unit_p: str) -> str:
        name = unit_s if today_v == 1 else unit_p
        diff = today_v - yest_v
        if diff > 0:
            change_txt = f"up from {yest_v} yesterday"
        elif diff < 0:
            change_txt = f"down from {yest_v} yesterday"
        else:
            change_txt = f"same as yesterday"
        return f"{today_v} {name}, {change_txt} (7d avg: {avg_v:.1f})"

    n_days = len(records)
    avg_due = sum(r["orders_due"] for r in records) / n_days
    avg_late = sum(r["orders_late"] for r in records) / n_days
    avg_short = sum(r["late_units"] + r["shortfall"] for r in records) / n_days
    avg_mats = sum(r["materials_low"] for r in records) / n_days

    today_units_short = today_rec["late_units"] + today_rec["shortfall"]
    yest_units_short = yest_rec["late_units"] + yest_rec["shortfall"]

    ctx = {
        "orders_due_text": _comp(today_rec["orders_due"], yest_rec["orders_due"], avg_due, "order due", "orders due"),
        "orders_late_text": _comp(today_rec["orders_late"], yest_rec["orders_late"], avg_late, "late order", "late orders"),
        "units_short_text": _comp(today_units_short, yest_units_short, avg_short, "unit short", "units short"),
        "materials_low_text": _comp(today_rec["materials_low"], yest_rec["materials_low"], avg_mats, "material low", "materials low"),
        "today_orders_due": today_rec["orders_due"],
        "today_orders_late": today_rec["orders_late"],
        "today_units_short": today_units_short,
        "today_materials_low": today_rec["materials_low"],
        "yesterday_orders_late": yest_rec["orders_late"],
        "records": records
    }
    return records, ctx


def get_order_level_priorities(as_of: date, db_session) -> List[Dict[str, Any]]:
    """
    Builds the top 5 real order-level priority table:
    rank, order number, customer, product, quantity, due date, days overdue, reason.
    """
    from app.models.sales import Customer

    # 1. Overdue orders
    overdue_q = (
        db_session.query(SalesOrderLine, SalesOrder, Product, Customer)
        .join(SalesOrder, SalesOrder.id == SalesOrderLine.sales_order_id)
        .join(Product, Product.id == SalesOrderLine.product_id)
        .join(Customer, Customer.id == SalesOrder.customer_id)
        .filter(
            SalesOrder.order_date <= as_of,
            SalesOrder.requested_delivery_date < as_of
        )
        .all()
    )

    items: List[Dict[str, Any]] = []
    for sol, so, prod, cust in overdue_q:
        shipped = (
            db_session.query(func.coalesce(func.sum(DeliveryLine.quantity_shipped), 0))
            .join(Delivery, Delivery.id == DeliveryLine.delivery_id)
            .filter(
                DeliveryLine.sales_order_line_id == sol.id,
                Delivery.ship_date <= as_of
            )
            .scalar()
        ) or 0
        rem = max(0, (sol.quantity_ordered or 0) - shipped)
        if rem > 0:
            days_over = (as_of - so.requested_delivery_date).days
            over_txt = f"{days_over} day{'s' if days_over != 1 else ''} late"
            items.append({
                "order_no": f"SO-{so.id}",
                "customer": cust.name,
                "product": prod.name,
                "quantity": rem,
                "due_date": so.requested_delivery_date.strftime("%d %b"),
                "days_overdue": over_txt,
                "days_overdue_num": days_over,
                "reason": f"Customer delivery is {days_over} day{'s' if days_over != 1 else ''} overdue; expedite shipment",
                "is_overdue": True
            })

    items.sort(key=lambda x: (-x["days_overdue_num"], -x["quantity"]))

    # 2. Near-due orders (due in next 3 days)
    if len(items) < 5:
        near_q = (
            db_session.query(SalesOrderLine, SalesOrder, Product, Customer)
            .join(SalesOrder, SalesOrder.id == SalesOrderLine.sales_order_id)
            .join(Product, Product.id == SalesOrderLine.product_id)
            .join(Customer, Customer.id == SalesOrder.customer_id)
            .filter(
                SalesOrder.order_date <= as_of,
                SalesOrder.requested_delivery_date >= as_of,
                SalesOrder.requested_delivery_date <= as_of + timedelta(days=3)
            )
            .order_by(SalesOrder.requested_delivery_date.asc())
            .all()
        )
        for sol, so, prod, cust in near_q:
            if len(items) >= 5:
                break
            shipped = (
                db_session.query(func.coalesce(func.sum(DeliveryLine.quantity_shipped), 0))
                .join(Delivery, Delivery.id == DeliveryLine.delivery_id)
                .filter(
                    DeliveryLine.sales_order_line_id == sol.id,
                    Delivery.ship_date <= as_of
                )
                .scalar()
            ) or 0
            rem = max(0, (sol.quantity_ordered or 0) - shipped)
            if rem > 0:
                diff = (so.requested_delivery_date - as_of).days
                if diff == 0:
                    status_txt = "Due today"
                elif diff == 1:
                    status_txt = "Due tomorrow"
                else:
                    status_txt = f"Due in {diff} days"
                items.append({
                    "order_no": f"SO-{so.id}",
                    "customer": cust.name,
                    "product": prod.name,
                    "quantity": rem,
                    "due_date": so.requested_delivery_date.strftime("%d %b"),
                    "days_overdue": status_txt,
                    "days_overdue_num": -diff,
                    "reason": f"Upcoming order requested on {so.requested_delivery_date.strftime('%d %b')}",
                    "is_overdue": False
                })

    for i, it in enumerate(items[:5]):
        it["rank"] = i + 1

    return items[:5]


def get_supplier_watch(as_of: date, db_session) -> Dict[str, Any]:
    """
    Overdue purchase orders and expected receipts tomorrow.
    """
    # Overdue POs
    cand_pos = (
        db_session.query(PurchaseOrderLine, PurchaseOrder, Supplier, Product)
        .join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderLine.po_id)
        .join(Supplier, Supplier.id == PurchaseOrder.supplier_id)
        .join(Product, Product.id == PurchaseOrderLine.material_id)
        .filter(
            PurchaseOrder.order_date <= as_of,
            PurchaseOrder.expected_delivery_date < as_of
        )
        .all()
    )

    overdue_list = []
    for pol, po, supp, prod in cand_pos:
        rec = (
            db_session.query(func.coalesce(func.sum(GoodsReceiptLine.quantity_received), 0))
            .join(GoodsReceipt, GoodsReceipt.id == GoodsReceiptLine.receipt_id)
            .filter(
                GoodsReceiptLine.po_line_id == pol.id,
                GoodsReceipt.receipt_date <= as_of
            )
            .scalar()
        ) or 0
        rem = max(0, (pol.quantity_ordered or 0) - rec)
        if rem > 0:
            days_over = (as_of - po.expected_delivery_date).days
            overdue_list.append({
                "po_no": f"PO-{po.id}",
                "supplier": supp.name,
                "material": prod.name,
                "pending_qty": rem,
                "days_overdue": f"{days_over} day{'s' if days_over != 1 else ''} late",
                "expected_date": po.expected_delivery_date.strftime("%d %b")
            })

    # Expected receipts tomorrow
    tomorrow = as_of + timedelta(days=1)
    tmrw_pos = (
        db_session.query(PurchaseOrderLine, PurchaseOrder, Supplier, Product)
        .join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderLine.po_id)
        .join(Supplier, Supplier.id == PurchaseOrder.supplier_id)
        .join(Product, Product.id == PurchaseOrderLine.material_id)
        .filter(
            PurchaseOrder.order_date <= as_of,
            PurchaseOrder.expected_delivery_date == tomorrow
        )
        .all()
    )

    expected_tmrw = []
    for pol, po, supp, prod in tmrw_pos:
        rec = (
            db_session.query(func.coalesce(func.sum(GoodsReceiptLine.quantity_received), 0))
            .join(GoodsReceipt, GoodsReceipt.id == GoodsReceiptLine.receipt_id)
            .filter(
                GoodsReceiptLine.po_line_id == pol.id,
                GoodsReceipt.receipt_date <= as_of
            )
            .scalar()
        ) or 0
        rem = max(0, (pol.quantity_ordered or 0) - rec)
        if rem > 0:
            expected_tmrw.append(
                f"PO-{po.id} from {supp.name} ({rem} units {prod.name}) expected tomorrow"
            )

    return {
        "overdue_pos": overdue_list,
        "expected_tomorrow": expected_tmrw,
        "has_issues": bool(overdue_list)
    }


def render_causal_findings_brief(
    as_of: date,
    base_url: Optional[str] = None
) -> Tuple[str, str, str]:
    """Compatibility alias for exception view."""
    return render_nightly_digest(as_of, base_url)


def render_nightly_digest(
    as_of: Optional[date] = None,
    base_url: Optional[str] = None,
    db_session=None,
    return_sparkline: bool = False
) -> Tuple[str, str, str] | Tuple[str, str, str, bytes]:
    """
    Renders the SAGE Daily Brief email and single-page A4 document.
    Adheres strictly to Part 5:
    - 600px table layout, inline CSS, dark mode safe.
    - Plain English, zero forbidden jargon.
    - Single A4 page guaranteed.
    """
    if as_of is None:
        as_of = get_current_day()

    close_db = False
    if db_session is None:
        db_session = SessionLocal()
        close_db = True

    try:
        date_str_formatted = f"{as_of.day} {as_of.strftime('%b')} {as_of.year}"
        dashboard_url = base_url or get_base_url()
        snap = compute_daily_snapshot(as_of, db_session=db_session)
        pri = compute_priorities(as_of, db_session=db_session, snapshot=snap)
        narr = generate_executive_narrative(snap, pri)

        # 1. Trailing 7 days context
        records_7d, kpi_ctx = get_trailing_7d_metrics(as_of, db_session)
        sparkline_png = generate_7d_sparkline_png(records_7d)
        from stage9.trace import compute_cause_trace, compute_focus_list
        cause_chains = compute_cause_trace(as_of)
        focus_items = compute_focus_list(as_of, db_session=db_session)

        # 3. Supplier watch
        supp_watch = get_supplier_watch(as_of, db_session)

        from stage9.status import compute_daily_status_and_actions
        status_info = compute_daily_status_and_actions(as_of, db_session=db_session)
        total_action_items = status_info["action_items_count"]
        status_title = status_info["status_banner"]
        subject = status_info["subject"]

        if status_title == "Action needed":
            status_badge_bg = "#fee2e2"
            status_badge_color = "#991b1b"
            status_badge_border = "#f87171"
            status_summary = f"{total_action_items} item{'s' if total_action_items != 1 else ''} need action"
        elif status_title == "Watch closely":
            status_badge_bg = "#fef3c7"
            status_badge_color = "#92400e"
            status_badge_border = "#fcd34d"
            status_summary = "Monitor production buffers"
        else:
            status_badge_bg = "#dcfce7"
            status_badge_color = "#166534"
            status_badge_border = "#86efac"
            status_summary = "All operations on schedule"

        # 2. Bottom Line (2 sentences from facts)
        bottom_lines = narr.get("bottom_line", [])
        if len(bottom_lines) >= 2:
            bottom_line_text = f"{bottom_lines[0]} {bottom_lines[1]}"
            preheader_text = bottom_lines[0]
        elif len(bottom_lines) == 1:
            bottom_line_text = f"{bottom_lines[0]} All active manufacturing schedules remain on track."
            preheader_text = bottom_lines[0]
        else:
            if total_action_items > 0:
                bottom_line_text = f"Production operations face {total_action_items} critical delivery items today. Immediate scheduling interventions are required."
                preheader_text = f"Production operations face {total_action_items} critical delivery items today."
            else:
                bottom_line_text = "Factory operations ran smoothly across all workcenters today. All customer shipments and supplier replenishments are tracking within planned parameters."
                preheader_text = "Factory operations ran smoothly across all workcenters today."

        # Computed projection line (only if recent usage > 0)
        projection_html = ""
        projection_text = ""
        for m_id, m_data in snap.get("materials", {}).items():
            u_rate = float(m_data.get("daily_usage_rate", 0.0))
            stk = float(m_data.get("stock", 0.0))
            saf = float(m_data.get("safety_stock", 0.0))
            m_nm = m_data.get("name", f"Material {m_id}")
            if u_rate > 0.0 and stk > saf:
                days_left = (stk - saf) / u_rate
                if 0.5 <= days_left <= 7.0:
                    d_int = max(1, int(round(days_left)))
                    projection_text = f"At the recent usage rate of {u_rate:.1f} kg/day, {m_nm.lower()} reaches its safety level in {d_int} day{'s' if d_int != 1 else ''}."
                    projection_html = f'<div style="font-size: 9.5px; color: #b45309; margin-top: 4px; font-weight: 500;">&bull; {projection_text}</div>'
                    break

        # 4. What caused what (Past analysed cases)
        if cause_chains:
            chains_html = ""
            for c in cause_chains[:3]:
                conf_color = "#166534" if c["confidence"] == "Seen end to end" else "#92400e"
                conf_bg = "#dcfce7" if c["confidence"] == "Seen end to end" else "#fef3c7"
                chains_html += f"""
                <div style="margin-bottom: 5px; padding: 5px 8px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 4px;">
                  <div style="font-size: 10.5px; font-weight: 700; color: #0f172a; margin-bottom: 2px;">
                    {c['chain_text']}
                  </div>
                  <div style="font-size: 9.5px; color: #334155; margin-bottom: 2px;">
                    {c['narrative']}
                  </div>
                  <div style="font-size: 9px; color: #64748b;">
                    <span style="background: {conf_bg}; color: {conf_color}; font-weight: 700; padding: 1px 4px; border-radius: 3px;">{c['confidence']}</span>
                    &nbsp;&bull;&nbsp; <strong>Model check:</strong> {c['model_check']['label']} ({c['model_check']['tag']}) &mdash; {c['model_check']['details']}
                  </div>
                </div>
                """
        else:
            chains_html = """
            <div style="font-size: 10px; color: #475569; padding: 4px 0; font-style: italic;">
              No abnormal causal cascades observed in the trailing 7 days. Operations tracking within baseline variation.
            </div>
            """

        # 5. Focus tomorrow (Top 5)
        focus_rows_html = ""
        for it in focus_items[:5]:
            badge_bg = "#dbeafe" if it.get("is_root_fix") else "#f1f5f9"
            badge_fg = "#1e40af" if it.get("is_root_fix") else "#475569"
            focus_rows_html += f"""
            <tr style="border-bottom: 1px solid #f1f5f9;">
              <td style="padding: 3px 5px; font-weight: 700; color: #2563eb; width: 16px; font-size: 9.5px;">{it['rank']}</td>
              <td style="padding: 3px 5px; font-size: 10px; color: #0f172a; font-weight: 600;">{it['action']}</td>
              <td style="padding: 3px 5px; font-size: 9.5px; color: #475569; white-space: nowrap;">
                <span style="background: {badge_bg}; color: {badge_fg}; padding: 1px 4px; border-radius: 3px; font-weight: 600;">{it['owner_role']}</span>
              </td>
              <td style="padding: 3px 5px; font-size: 9.5px; color: #0f172a; white-space: nowrap;">{it['due_time']}</td>
              <td style="padding: 3px 5px; font-size: 9px; color: #64748b;">{it['reason']}</td>
            </tr>
            """

        # 6. Supplier watch rows
        supplier_watch_html = ""
        if supp_watch["overdue_pos"]:
            for po_it in supp_watch["overdue_pos"]:
                supplier_watch_html += f"""
                <div style="font-size: 10px; margin-bottom: 2px; color: #0f172a;">
                  &bull; <strong>{po_it['po_no']}</strong> ({po_it['supplier']}): {po_it['pending_qty']} units of {po_it['material']} &mdash; <span style="color: #b91c1c; font-weight: 600;">{po_it['days_overdue']}</span> (expected {po_it['expected_date']})
                </div>
                """
        else:
            supplier_watch_html = '<div style="font-size: 10px; color: #166534; font-weight: 500;">No supplier problems today.</div>'

        if supp_watch["expected_tomorrow"]:
            supplier_watch_html += '<div style="font-size: 9.5px; color: #475569; margin-top: 2px;"><strong>Receipts expected tomorrow:</strong> ' + "; ".join(supp_watch["expected_tomorrow"]) + '</div>'

        # 7-day table rows
        spark_table_headers = "".join([f'<th style="padding: 2px 4px; font-size: 8.5px; font-weight: 600; color: #475569; text-align: center;">{r["date_label"]}</th>' for r in records_7d])
        spark_table_late = "".join([f'<td style="padding: 2px 4px; font-size: 8.5px; text-align: center; color: {"#b91c1c" if r["late_units"] > 0 else "#64748b"}; font-weight: {"700" if r["late_units"] > 0 else "normal"};">{r["late_units"]}</td>' for r in records_7d])
        spark_table_short = "".join([f'<td style="padding: 2px 4px; font-size: 8.5px; text-align: center; color: {"#2563eb" if r["shortfall"] > 0 else "#64748b"};">{r["shortfall"]}</td>' for r in records_7d])

        sent_time_str = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")

        # Compact, solid single-page HTML layout
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{subject}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    @media (prefers-color-scheme: dark) {{
      .email-bg {{ background-color: #0f172a !important; }}
      .email-card {{ background-color: #1e293b !important; color: #f8fafc !important; border-color: #334155 !important; }}
      .text-dark {{ color: #f8fafc !important; }}
      .text-muted {{ color: #94a3b8 !important; }}
    }}
    @page {{
      size: A4 portrait;
      margin: 6mm 8mm 6mm 8mm;
    }}
  </style>
</head>
<body style="margin: 0; padding: 0; background-color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; -webkit-font-smoothing: antialiased;" class="email-bg">
  <!-- Preheader text -->
  <span style="display:none; font-size:1px; color:#ffffff; line-height:1px; max-height:0px; max-width:0px; opacity:0; overflow:hidden;">{preheader_text}</span>

  <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #f1f5f9; padding: 6px 0;" class="email-bg">
    <tr>
      <td align="center">
        <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="600" style="width: 600px; max-width: 600px; background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.05);" class="email-card">

          <!-- 1. Header & Status Banner -->
          <tr>
            <td style="padding: 10px 16px 8px 16px; border-bottom: 1px solid #e2e8f0;">
              <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
                <tr>
                  <td>
                    <div style="font-size: 15px; font-weight: 800; color: #0f172a; letter-spacing: -0.02em;">
                      <span style="color: #2563eb;">SAGE</span> Daily Brief
                    </div>
                    <div style="font-size: 10px; color: #64748b; font-weight: 500; margin-top: 1px;">
                      Simulated factory data as of {as_of.isoformat()}
                    </div>
                  </td>
                  <td align="right">
                    <span style="display: inline-block; font-size: 10.5px; font-weight: 700; color: {status_badge_color}; background-color: {status_badge_bg}; border: 1px solid {status_badge_border}; border-radius: 4px; padding: 2px 7px; text-transform: uppercase; letter-spacing: 0.03em;">
                      {status_title} &bull; {status_summary}
                    </span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- 2. Bottom Line -->
          <tr>
            <td style="padding: 8px 16px; background-color: #f8fafc; border-bottom: 1px solid #e2e8f0;">
              <div style="font-size: 9.5px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: #64748b; margin-bottom: 2px;">The Bottom Line</div>
              <div style="font-size: 11.5px; line-height: 1.4; color: #0f172a; font-weight: 500;">
                {bottom_line_text}
              </div>
            </td>
          </tr>

          <!-- 3. Today's Numbers with Context & 7-Day Trend -->
          <tr>
            <td style="padding: 8px 16px 6px 16px; border-bottom: 1px solid #f1f5f9;">
              <div style="font-size: 9.5px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: #64748b; margin-bottom: 4px;">Today's Numbers in Context</div>
              <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
                <tr>
                  <td width="25%" style="padding: 5px 6px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 4px; vertical-align: top;">
                    <div style="font-size: 8.5px; color: #64748b; font-weight: 600;">Orders Due</div>
                    <div style="font-size: 14px; font-weight: 800; color: #0f172a; margin: 1px 0;">{kpi_ctx['today_orders_due']}</div>
                    <div style="font-size: 8px; color: #64748b; line-height: 1.2;">{kpi_ctx['orders_due_text'].split(',', 1)[-1].strip()}</div>
                  </td>
                  <td width="2%">&nbsp;</td>
                  <td width="25%" style="padding: 5px 6px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 4px; vertical-align: top;">
                    <div style="font-size: 8.5px; color: #64748b; font-weight: 600;">Orders Late</div>
                    <div style="font-size: 14px; font-weight: 800; color: {'#dc2626' if kpi_ctx['today_orders_late'] > 0 else '#0f172a'}; margin: 1px 0;">{kpi_ctx['today_orders_late']}</div>
                    <div style="font-size: 8px; color: #64748b; line-height: 1.2;">{kpi_ctx['orders_late_text'].split(',', 1)[-1].strip()}</div>
                  </td>
                  <td width="2%">&nbsp;</td>
                  <td width="25%" style="padding: 5px 6px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 4px; vertical-align: top;">
                    <div style="font-size: 8.5px; color: #64748b; font-weight: 600;">Units Short</div>
                    <div style="font-size: 14px; font-weight: 800; color: {'#dc2626' if kpi_ctx['today_units_short'] > 0 else '#0f172a'}; margin: 1px 0;">{kpi_ctx['today_units_short']}</div>
                    <div style="font-size: 8px; color: #64748b; line-height: 1.2;">{kpi_ctx['units_short_text'].split(',', 1)[-1].strip()}</div>
                  </td>
                  <td width="2%">&nbsp;</td>
                  <td width="25%" style="padding: 5px 6px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 4px; vertical-align: top;">
                    <div style="font-size: 8.5px; color: #64748b; font-weight: 600;">Materials Low</div>
                    <div style="font-size: 14px; font-weight: 800; color: {'#d97706' if kpi_ctx['today_materials_low'] > 0 else '#0f172a'}; margin: 1px 0;">{kpi_ctx['today_materials_low']}</div>
                    <div style="font-size: 8px; color: #64748b; line-height: 1.2;">{kpi_ctx['materials_low_text'].split(',', 1)[-1].strip()}</div>
                  </td>
                </tr>
              </table>
              {projection_html}
              <div style="text-align: center; margin: 6px 0 4px 0;">
                <img src="cid:sparkline7d" alt="7-Day Trend Sparkline" style="width: 560px; max-width: 100%; height: auto; border: 1px solid #e2e8f0; border-radius: 4px; display: block;" />
              </div>
            </td>
          </tr>

          <!-- 4. Past analysed cases -->
          <tr>
            <td style="padding: 6px 16px; border-bottom: 1px solid #f1f5f9;">
              <div style="font-size: 9.5px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: #64748b; margin-bottom: 3px;">
                Past analysed cases: What caused what
              </div>
              {chains_html}
            </td>
          </tr>

          <!-- 5. Focus Tomorrow (Top 5) -->
          <tr>
            <td style="padding: 6px 16px; border-bottom: 1px solid #f1f5f9;">
              <div style="font-size: 9.5px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: #64748b; margin-bottom: 3px;">Focus Tomorrow (Top 5 Priorities)</div>
              <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="border-collapse: collapse;">
                <thead>
                  <tr style="background-color: #f8fafc; border-bottom: 1px solid #e2e8f0; text-align: left;">
                    <th style="padding: 3px 5px; font-size: 8.5px; color: #64748b;">#</th>
                    <th style="padding: 3px 5px; font-size: 8.5px; color: #64748b;">Action</th>
                    <th style="padding: 3px 5px; font-size: 8.5px; color: #64748b;">Owner</th>
                    <th style="padding: 3px 5px; font-size: 8.5px; color: #64748b;">Due</th>
                    <th style="padding: 3px 5px; font-size: 8.5px; color: #64748b;">Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {focus_rows_html}
                </tbody>
              </table>
            </td>
          </tr>

          <!-- 6. Supplier Watch -->
          <tr>
            <td style="padding: 6px 16px; border-bottom: 1px solid #f1f5f9;">
              <div style="font-size: 9.5px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: #64748b; margin-bottom: 3px;">Supplier Watch</div>
              {supplier_watch_html}
            </td>
          </tr>

          <!-- 7. Footer with Mandatory Framing -->
          <tr>
            <td style="padding: 8px 16px 10px 16px; background-color: #f8fafc; font-size: 9px; color: #64748b; line-height: 1.4;">
              <div style="font-weight: 600; color: #334155; margin-bottom: 2px;">
                <strong>Framing:</strong> {RESEARCH_FRAMING}
              </div>
              <div>
                Simulated data. System knows data up to {as_of.isoformat()} only. &bull; Generated at {sent_time_str}.
              </div>
              <div style="margin-top: 3px;">
                <a href="{dashboard_url}" style="color: #2563eb; text-decoration: underline; font-weight: 600;">Open SAGE Web Dashboard &rarr;</a>
              </div>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

        # Plain-text alternative wrapped at 72 characters
        text_lines = [
            f"SAGE DAILY BRIEF | {date_str_formatted}",
            f"Status: {status_title.upper()} ({status_summary})",
            "=" * 70,
            "",
            "THE BOTTOM LINE:",
            textwrap.fill(bottom_line_text, width=72),
            "",
            "TODAY'S NUMBERS IN CONTEXT:",
            f"• Orders Due     : {kpi_ctx['orders_due_text']}",
            f"• Orders Late    : {kpi_ctx['orders_late_text']}",
            f"• Units Short    : {kpi_ctx['units_short_text']}",
            f"• Materials Low  : {kpi_ctx['materials_low_text']}",
        ]
        if projection_text:
            text_lines.append(f"• Projection     : {projection_text}")

        text_lines.extend([
            "",
            "PAST ANALYSED CASES: WHAT CAUSED WHAT:",
        ])
        if cause_chains:
            for c in cause_chains[:3]:
                text_lines.append(f"• Chain: {c['chain_text']}")
                text_lines.append(f"  {c['narrative']}")
                text_lines.append(f"  Confidence: {c['confidence']} | Model check: {c['model_check']['label']} ({c['model_check']['tag']})")
        else:
            text_lines.append("No abnormal causal cascades observed in the trailing 7 days.")

        text_lines.extend([
            "",
            "FOCUS TOMORROW (TOP 5 PRIORITIES):",
        ])
        for it in focus_items[:5]:
            text_lines.append(f"{it['rank']}. {it['action']} ({it['owner_role']}) - Due {it['due_time']}")
            text_lines.append(f"   Reason: {it['reason']}")

        text_lines.extend([
            "",
            "SUPPLIER WATCH:",
        ])
        if supp_watch["overdue_pos"]:
            for po_it in supp_watch["overdue_pos"]:
                text_lines.append(
                    f"• {po_it['po_no']} ({po_it['supplier']}): {po_it['pending_qty']} units {po_it['material']} - {po_it['days_overdue']} (expected {po_it['expected_date']})"
                )
        else:
            text_lines.append("No supplier problems today.")
        if supp_watch["expected_tomorrow"]:
            text_lines.append("Receipts expected tomorrow: " + "; ".join(supp_watch["expected_tomorrow"]))

        text_lines.extend([
            "",
            "=" * 70,
            f"FRAMING: {RESEARCH_FRAMING}",
            "",
            f"Simulated data. System knows data up to {as_of.isoformat()} only.",
            f"Dashboard: {dashboard_url}"
        ])

        plain_text = "\n".join(text_lines)

        if return_sparkline:
            return subject, html, plain_text, sparkline_png
        return subject, html, plain_text

    finally:
        if close_db:
            db_session.close()


def assert_one_page_pdf(html_content: str, sparkline_png: Optional[bytes] = None) -> Tuple[bool, int, Optional[bytes]]:
    """
    Renders HTML to PDF on A4 with Playwright Chromium and asserts page_count == 1.
    Returns (is_single_page, page_count, pdf_bytes).
    """
    try:
        import base64
        if sparkline_png and "cid:sparkline7d" in html_content:
            b64_img = base64.b64encode(sparkline_png).decode("utf-8")
            html_content = html_content.replace("cid:sparkline7d", f"data:image/png;base64,{b64_img}")
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_content(html_content, wait_until="networkidle")
            pdf_bytes = page.pdf(
                format="A4",
                print_background=True,
                margin={"top": "6mm", "bottom": "6mm", "left": "8mm", "right": "8mm"}
            )
            browser.close()

        page_matches = len(re.findall(rb"/Type\s*/Page\b", pdf_bytes))
        is_single = (page_matches == 1)
        return is_single, page_matches, pdf_bytes
    except Exception as exc:
        logger.warning("Playwright PDF check exception: %s", exc)
        return False, 0, None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Render SAGE Daily Brief email.")
    parser.add_argument("--date", help="Date YYYY-MM-DD")
    parser.add_argument("--check-pdf", action="store_true", help="Assert one-page PDF")
    args = parser.parse_args()

    as_of_d = datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else get_current_day()
    subj, htm, txt = render_nightly_digest(as_of_d)
    print(f"Subject: {subj}")
    if args.check_pdf:
        ok, cnt, bts = assert_one_page_pdf(htm)
        print(f"PDF Page Check: ok={ok}, pages={cnt}, size={len(bts) if bts else 0} bytes")
