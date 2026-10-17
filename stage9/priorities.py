"""
stage9/priorities.py — SAGE Phase B: Deterministic Priorities Engine.

Rules-Only Deterministic Action List (Strict Data Grounding):
────────────────────────────────────────────────────────────────────────────
1. Orders already overdue:
   - Rank by days_overdue DESC, then pending units DESC.
   - Action: "Fulfil order SO-<id> first"
   - Role: "Planner"
2. Orders due within 1–3 days where projected availability is insufficient:
   - Action: "At risk: Order SO-<id>"
   - Role: "Planner"
3. Materials at/below safety stock, or at/below reorder point with no open PO:
   - Action: "Expedite urgent replenishment for <Material>"
   - Role: "Procurement"
4. Open POs overdue:
   - Rank by days_overdue DESC.
   - Action: "Chase supplier <Supplier> (PO-<id>)"
   - Role: "Procurement"
5. Yesterday's production shortfall:
   - Action: "Review capacity & throughput for <Product>"
   - Role: "Plant Manager"

Forward-Looking Calm-Day Fillers (Strictly Grounded in Data, Zero Make-Believe):
────────────────────────────────────────────────────────────────────────────
If rules 1–5 yield fewer than 5 items, forward-looking items from real data:
a. Orders due in the next 3 days.
b. Next purchase-order arrivals.
c. The 2 materials with lowest days of cover.
If none exist, action is: "Nothing needs action tomorrow."
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import func
from app.database import SessionLocal
from app.models.inventory import InventoryItem, Product, StockMovement
from app.models.suppliers import Supplier
from app.models.purchasing import PurchaseOrder, PurchaseOrderLine, GoodsReceipt, GoodsReceiptLine
from app.models.production import ProductionOrder
from app.models.sales import SalesOrder, SalesOrderLine, Delivery, DeliveryLine
from stage9.clock import get_as_of_date
from stage9.snapshot import compute_daily_snapshot

PRIORITIES_DIR = ROOT_DIR / "analytics" / "priorities"
RULES_FILE = ROOT_DIR / "stage9" / "config" / "rules.yaml"


def format_material_display(name: str, item_id: Any) -> str:
    s_id = str(item_id)
    if "Material" in name or f"({s_id})" in name:
        return name
    return f"{name} (Material {s_id})"


def format_product_display(name: str, prod_id: Any) -> str:
    s_id = str(prod_id)
    if "Product" in name or f"({s_id})" in name:
        return name
    return f"{name} (Product {s_id})"


def compute_priorities(
    as_of: date,
    snapshot: Optional[Dict[str, Any]] = None,
    db_session=None,
    output_dir: Optional[Path] = None,
    source: Optional[str] = None
) -> Dict[str, Any]:
    """
    Computes a deterministic action list and watchlist for the day following as_of.
    Every item is strictly grounded in data; zero filler/invented tasks.
    """
    close_session = False
    if db_session is None:
        db_session = SessionLocal(source=source)
        close_session = True

    try:
        if snapshot is None:
            snapshot = compute_daily_snapshot(as_of, db_session=db_session, source=source)

        candidate_actions: List[Dict[str, Any]] = []
        watchlist_candidates: List[Dict[str, Any]] = []

        # ──────────────────────────────────────────────────────────────────────
        # Rule 1: Orders already overdue (rank by days overdue, then units)
        # ──────────────────────────────────────────────────────────────────────
        overdue_orders = (
            db_session.query(SalesOrderLine, SalesOrder, Product)
            .join(SalesOrder, SalesOrder.id == SalesOrderLine.sales_order_id)
            .join(Product, Product.id == SalesOrderLine.product_id)
            .filter(
                SalesOrder.order_date <= as_of,
                SalesOrder.requested_delivery_date < as_of
            )
            .all()
        )

        overdue_list = []
        for so_line, so, prod in overdue_orders:
            shipped_qty = (
                db_session.query(func.coalesce(func.sum(DeliveryLine.quantity_shipped), 0))
                .join(Delivery, Delivery.id == DeliveryLine.delivery_id)
                .filter(
                    DeliveryLine.sales_order_line_id == so_line.id,
                    Delivery.ship_date <= as_of
                )
                .scalar()
            ) or 0
            pending = max(0, (so_line.quantity_ordered or 0) - shipped_qty)
            if pending > 0:
                days_over = (as_of - so.requested_delivery_date).days
                p_display = format_product_display(prod.name, prod.id)
                overdue_list.append({
                    "rule": 1,
                    "so_id": so.id,
                    "days_overdue": days_over,
                    "pending_units": pending,
                    "product_name": p_display,
                    "due_date": so.requested_delivery_date.isoformat(),
                    "action": f"Fulfil order SO-{so.id} first",
                    "reason": f"Order SO-{so.id} for {p_display} is {days_over} days overdue ({pending} units pending, due {so.requested_delivery_date.isoformat()})",
                    "role": "Planner",
                    "target_due": as_of.isoformat()
                })

        overdue_list.sort(key=lambda x: (-x["days_overdue"], -x["pending_units"]))
        candidate_actions.extend(overdue_list)

        # ──────────────────────────────────────────────────────────────────────
        # Rule 2: Orders due within 1–3 days where projected availability is short
        # ──────────────────────────────────────────────────────────────────────
        horizon_end = as_of + timedelta(days=3)
        near_due_orders = (
            db_session.query(SalesOrderLine, SalesOrder, Product)
            .join(SalesOrder, SalesOrder.id == SalesOrderLine.sales_order_id)
            .join(Product, Product.id == SalesOrderLine.product_id)
            .filter(
                SalesOrder.order_date <= as_of,
                SalesOrder.requested_delivery_date > as_of,
                SalesOrder.requested_delivery_date <= horizon_end
            )
            .order_by(SalesOrder.requested_delivery_date.asc())
            .all()
        )

        for so_line, so, prod in near_due_orders:
            p_id = str(so_line.product_id)
            p_snap = snapshot.get("products", {}).get(p_id, {})
            current_fg = float(p_snap.get("fg_stock", 0.0))
            planned_prod = float(p_snap.get("planned_production", 0.0))
            projected_avail = current_fg + planned_prod

            shipped_qty = (
                db_session.query(func.coalesce(func.sum(DeliveryLine.quantity_shipped), 0))
                .join(Delivery, Delivery.id == DeliveryLine.delivery_id)
                .filter(
                    DeliveryLine.sales_order_line_id == so_line.id,
                    Delivery.ship_date <= as_of
                )
                .scalar()
            ) or 0
            pending = max(0, (so_line.quantity_ordered or 0) - shipped_qty)
            if pending > 0:
                days_ahead = (so.requested_delivery_date - as_of).days
                p_display = format_product_display(prod.name, prod.id)
                if projected_avail < pending:
                    candidate_actions.append({
                        "rule": 2,
                        "so_id": so.id,
                        "action": f"At risk: Order SO-{so.id}",
                        "reason": f"Order SO-{so.id} ({p_display}) due in {days_ahead} days ({pending} units) exceeds projected availability of {int(projected_avail)} units",
                        "role": "Planner",
                        "target_due": so.requested_delivery_date.isoformat(),
                        "severity_weight": 20.0 + pending
                    })
                else:
                    if projected_avail - pending <= 10:
                        watchlist_candidates.append({
                            "item": f"Tight buffer on SO-{so.id} ({p_display})",
                            "reason": f"Order due {so.requested_delivery_date.isoformat()} has only {int(projected_avail - pending)} units cushion above planned fulfillment",
                            "role": "Planner"
                        })

        # ──────────────────────────────────────────────────────────────────────
        # Rule 3: Materials at or below safety stock or reorder point
        # ──────────────────────────────────────────────────────────────────────
        for m_id, m_data in snapshot.get("materials", {}).items():
            stock = float(m_data["stock"])
            safety = float(m_data["safety_stock"])
            reorder = float(m_data["reorder_point"])
            open_pos = int(m_data["open_pos_count"])
            name_display = format_material_display(m_data["name"], m_id)

            if stock <= safety:
                cov_desc = f"Cover is {m_data['days_of_cover']} days" if m_data.get("days_of_cover") is not None else "no recent use"
                candidate_actions.append({
                    "rule": 3,
                    "action": f"Expedite urgent replenishment for {name_display}",
                    "reason": f"{name_display} stock at {int(stock)} kg is at or below safety stock ({int(safety)} kg). {cov_desc}",
                    "role": "Procurement",
                    "target_due": as_of.isoformat(),
                    "severity_weight": 30.0 + (safety - stock)
                })
            elif stock <= reorder and open_pos == 0:
                candidate_actions.append({
                    "rule": 3,
                    "action": f"Reorder {name_display}",
                    "reason": f"{name_display} stock at {int(stock)} kg is at or below reorder point ({int(reorder)} kg) with 0 open purchase orders",
                    "role": "Procurement",
                    "target_due": as_of.isoformat(),
                    "severity_weight": 15.0
                })
            elif stock <= reorder and open_pos > 0:
                watchlist_candidates.append({
                    "item": f"{name_display} inventory monitoring",
                    "reason": f"{name_display} is at {int(stock)} kg (below reorder point {int(reorder)} kg), tracking {open_pos} open replenishment POs",
                    "role": "Procurement"
                })

        # ──────────────────────────────────────────────────────────────────────
        # Rule 4: Open POs overdue (rank by days overdue)
        # ──────────────────────────────────────────────────────────────────────
        for m_id, m_data in snapshot.get("materials", {}).items():
            name_display = format_material_display(m_data["name"], m_id)
            for po_entry in m_data.get("overdue_pos", []):
                days_over = po_entry["days_overdue"]
                candidate_actions.append({
                    "rule": 4,
                    "po_id": po_entry["po_id"],
                    "days_overdue": days_over,
                    "action": f"Chase supplier {po_entry['supplier_name']} (PO-{po_entry['po_id']})",
                    "reason": f"PO-{po_entry['po_id']} for {name_display} ({po_entry['pending_quantity']} units) is {days_over} days overdue from {po_entry['supplier_name']}",
                    "role": "Procurement",
                    "target_due": as_of.isoformat(),
                    "severity_weight": 10.0 + (days_over * 2.0)
                })

        # ──────────────────────────────────────────────────────────────────────
        # Rule 5: Production shortfall
        # ──────────────────────────────────────────────────────────────────────
        for p_id, p_data in snapshot.get("products", {}).items():
            shortfall = int(p_data.get("production_shortfall", 0))
            if shortfall > 0:
                p_display = format_product_display(p_data["name"], p_id)
                candidate_actions.append({
                    "rule": 5,
                    "product_id": p_id,
                    "action": f"Review capacity & throughput for {p_display}",
                    "reason": f"{p_display} manufactured {p_data['actual_production']} units vs {p_data['planned_production']} planned ({shortfall} units shortfall)",
                    "role": "Plant Manager",
                    "target_due": as_of.isoformat(),
                    "severity_weight": 5.0 + shortfall
                })

        # Sort candidate actions by rule hierarchy
        candidate_actions.sort(key=lambda x: (x["rule"], -x.get("days_overdue", 0), -x.get("severity_weight", 0)))

        top_5: List[Dict[str, Any]] = []
        for idx, act in enumerate(candidate_actions[:5], start=1):
            top_5.append({
                "rank": idx,
                "action": act["action"],
                "reason": act["reason"],
                "role": act["role"],
                "due_date": act["target_due"],
                "category": f"Rule {act['rule']}"
            })

        # ──────────────────────────────────────────────────────────────────────
        # Forward-Looking Calm-Day Fillers (Data-Driven Only)
        # If fewer than 5 priorities, populate with genuine forward-looking data:
        # 1. Orders due in the next 3 days
        # 2. Next purchase-order arrivals
        # 3. The 2 materials with the lowest days of cover
        # ──────────────────────────────────────────────────────────────────────
        if len(top_5) < 5:
            existing_actions_text = {p["action"] for p in top_5}
            forward_items: List[Dict[str, Any]] = []

            # 1. Orders due in next 3 days (not already in top_5, pending > 0)
            for so_line, so, prod in near_due_orders:
                shipped_qty = (
                    db_session.query(func.coalesce(func.sum(DeliveryLine.quantity_shipped), 0))
                    .join(Delivery, Delivery.id == DeliveryLine.delivery_id)
                    .filter(
                        DeliveryLine.sales_order_line_id == so_line.id,
                        Delivery.ship_date <= as_of
                    )
                    .scalar()
                ) or 0
                pending = max(0, (so_line.quantity_ordered or 0) - shipped_qty)
                if pending <= 0:
                    continue
                p_display = format_product_display(prod.name, prod.id)
                act_str = f"Prepare dispatch for order SO-{so.id} ({p_display})"
                if act_str not in existing_actions_text:
                    forward_items.append({
                        "action": act_str,
                        "reason": f"Order SO-{so.id} ({pending} units) requested for delivery on {so.requested_delivery_date.isoformat()}",
                        "role": "Planner",
                        "due_date": so.requested_delivery_date.isoformat(),
                        "category": "Upcoming Order"
                    })

            # 2. Next purchase-order arrivals (open POs expected on or after as_of)
            upcoming_pos = (
                db_session.query(PurchaseOrderLine, PurchaseOrder, Supplier, Product)
                .join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderLine.po_id)
                .join(Supplier, Supplier.id == PurchaseOrder.supplier_id)
                .join(Product, Product.id == PurchaseOrderLine.material_id)
                .filter(
                    PurchaseOrder.order_date <= as_of,
                    PurchaseOrder.expected_delivery_date >= as_of
                )
                .order_by(PurchaseOrder.expected_delivery_date.asc())
                .all()
            )

            for po_line, po, supp, prod in upcoming_pos:
                rec_by_as_of = (
                    db_session.query(func.coalesce(func.sum(GoodsReceiptLine.quantity_received), 0))
                    .join(GoodsReceipt, GoodsReceipt.id == GoodsReceiptLine.receipt_id)
                    .filter(
                        GoodsReceiptLine.po_line_id == po_line.id,
                        GoodsReceipt.receipt_date <= as_of
                    )
                    .scalar()
                ) or 0
                rem_qty = max(0, (po_line.quantity_ordered or 0) - rec_by_as_of)
                if rem_qty <= 0:
                    continue
                m_display = format_material_display(prod.name, prod.id)
                act_str = f"Prepare receipt for PO-{po.id} from {supp.name}"
                if act_str not in existing_actions_text:
                    forward_items.append({
                        "action": act_str,
                        "reason": f"Expected shipment of {rem_qty} units of {m_display} scheduled for arrival on {po.expected_delivery_date.isoformat()}",
                        "role": "Procurement",
                        "due_date": po.expected_delivery_date.isoformat(),
                        "category": "Incoming Supply"
                    })

            # 3. The 2 materials with the lowest days of cover (or no recent use)
            mat_list = []
            for m_id, m_data in snapshot.get("materials", {}).items():
                cov = m_data.get("days_of_cover")
                cov_sort = float(cov) if cov is not None else 9999.0
                mat_list.append((cov_sort, m_id, m_data))
            mat_list.sort(key=lambda x: x[0])

            for cover, m_id, m_data in mat_list[:2]:
                m_display = format_material_display(m_data["name"], m_id)
                act_str = f"Monitor inventory buffer for {m_display}"
                if act_str not in existing_actions_text:
                    if m_data.get("days_of_cover") is not None:
                        reason_str = f"{m_display} has {m_data['days_of_cover']} days of cover remaining ({int(m_data['stock'])} kg on hand)"
                    else:
                        reason_str = f"{m_display} has no recent use ({int(m_data['stock'])} kg on hand)"
                    forward_items.append({
                        "action": act_str,
                        "reason": reason_str,
                        "role": "Procurement",
                        "due_date": as_of.isoformat(),
                        "category": "Buffer Health"
                    })

            # Append forward-looking items up to 5
            for f_item in forward_items:
                if len(top_5) >= 5:
                    break
                if f_item["action"] not in existing_actions_text:
                    existing_actions_text.add(f_item["action"])
                    top_5.append({
                        "rank": len(top_5) + 1,
                        "action": f_item["action"],
                        "reason": f_item["reason"],
                        "role": f_item["role"],
                        "due_date": f_item["due_date"],
                        "category": f_item["category"]
                    })

        # If absolutely nothing needs action from data, write the single plain truth:
        if not top_5:
            top_5.append({
                "rank": 1,
                "action": "Nothing needs action tomorrow.",
                "reason": "All customer orders fulfilled, inventory buffers healthy, and supplier deliveries tracking on schedule.",
                "role": "Operations",
                "due_date": as_of.isoformat(),
                "category": "Clear Status"
            })

        # Watch-list: Up to 3 items from excess real candidates
        watchlist: List[Dict[str, Any]] = []
        for extra in candidate_actions[5:]:
            if len(watchlist) >= 3:
                break
            watchlist.append({
                "item": extra["action"],
                "reason": extra["reason"],
                "role": extra["role"]
            })

        for w in watchlist_candidates:
            if len(watchlist) >= 3:
                break
            if not any(x["item"] == w["item"] for x in watchlist):
                watchlist.append(w)

        payload = {
            "as_of": as_of.isoformat(),
            "top_priorities": top_5,
            "watchlist": watchlist[:3],
            "metadata": {
                "as_of_date": as_of.isoformat(),
                "simulated_data": True,
                "rules_source": "stage9/config/rules.yaml"
            }
        }

        target_dir = output_dir or PRIORITIES_DIR
        target_dir.mkdir(parents=True, exist_ok=True)
        out_file = target_dir / f"priorities_{as_of.isoformat()}.json"

        content = json.dumps(payload, indent=2, sort_keys=True)
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(content + "\n")

        return payload

    finally:
        if close_session:
            db_session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SAGE Priorities Engine")
    parser.add_argument("--as-of", type=str, help="As-of date override (YYYY-MM-DD)")
    args = parser.parse_args()

    as_of_date = get_as_of_date(override=args.as_of)
    print(f"Generating priorities for as-of date: {as_of_date.isoformat()}...")
    res = compute_priorities(as_of_date)
    print(f"Priorities created successfully: analytics/priorities/priorities_{as_of_date.isoformat()}.json")
    print("\n--- TOP PRIORITIES ---")
    for p in res["top_priorities"]:
        print(f"[{p['rank']}] {p['action']} ({p['role']}) -> {p['reason']}")
    print("\n--- WATCHLIST ---")
    for w in res["watchlist"]:
        print(f"• {w['item']} -> {w['reason']}")
