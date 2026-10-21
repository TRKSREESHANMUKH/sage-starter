"""
stage9/priorities.py — SAGE Phase B: Deterministic Priorities Engine.

Rules-Only Deterministic Top-5 Action List:
────────────────────────────────────────────────────────────────────────────
1. Orders already overdue:
   - Rank by days_overdue DESC, then pending units DESC.
   - Action: "Fulfil order SO-<id> first"
   - Owner: "Planner"
2. Orders due within 1–3 days at risk:
   - Condition: projected_fg_stock + planned_production < units_due.
   - Action: "At risk: Order SO-<id>"
   - Owner: "Planner"
3. Materials at/below safety_stock, or at/below reorder_point with no open PO:
   - Action: "Expedite or reorder <Material>"
   - Owner: "Procurement"
4. Open POs overdue:
   - Rank by days_overdue DESC.
   - Action: "Chase supplier <Supplier>"
   - Owner: "Procurement"
5. Yesterday's production shortfall with a capacity cause:
   - Condition: production_shortfall > 0.
   - Action: "Review capacity for <Product>"
   - Owner: "Plant Manager"

Output:
- analytics/priorities/priorities_<date>.json
- Contains top 5 ranked actions, each with (rank, action, reason, role, due_date).
- Plus a watch-list of up to 3 items that are not yet critical.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import func
from app.database import SessionLocal
from app.models.inventory import InventoryItem, Product, StockMovement
from app.models.suppliers import Supplier
from app.models.purchasing import PurchaseOrder, PurchaseOrderLine
from app.models.production import ProductionOrder
from app.models.sales import SalesOrder, SalesOrderLine
from stage9.clock import get_as_of_date
from stage9.snapshot import compute_daily_snapshot

PRIORITIES_DIR = ROOT_DIR / "analytics" / "priorities"
RULES_FILE = ROOT_DIR / "stage9" / "config" / "rules.yaml"


def compute_priorities(
    as_of: date,
    snapshot: Optional[Dict[str, Any]] = None,
    db_session=None,
    output_dir: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Computes a deterministic Top-5 action list and up to 3 watch-list items
    for the day following as_of.
    """
    close_session = False
    if db_session is None:
        db_session = SessionLocal()
        close_session = True

    try:
        if snapshot is None:
            snapshot = compute_daily_snapshot(as_of, db_session=db_session)

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
                SalesOrder.requested_delivery_date < as_of,
                SalesOrder.status != "FULFILLED"
            )
            .all()
        )

        overdue_list = []
        for so_line, so, prod in overdue_orders:
            pending = max(0, (so_line.quantity_ordered or 0) - (so_line.quantity_fulfilled or 0))
            if pending > 0:
                days_over = (as_of - so.requested_delivery_date).days
                overdue_list.append({
                    "rule": 1,
                    "so_id": so.id,
                    "days_overdue": days_over,
                    "pending_units": pending,
                    "product_name": prod.name,
                    "due_date": so.requested_delivery_date.isoformat(),
                    "action": f"Fulfil order SO-{so.id} first",
                    "reason": f"Order SO-{so.id} for {prod.name} is {days_over} days overdue ({pending} units pending, due {so.requested_delivery_date.isoformat()})",
                    "role": "Planner",
                    "target_due": as_of.isoformat()
                })

        # Sort Rule 1 by days_overdue DESC, pending_units DESC
        overdue_list.sort(key=lambda x: (-x["days_overdue"], -x["pending_units"]))
        candidate_actions.extend(overdue_list)

        # ──────────────────────────────────────────────────────────────────────
        # Rule 2: Orders due within 1–3 days where projected stock < units due
        # ──────────────────────────────────────────────────────────────────────
        horizon_end = as_of + timedelta(days=3)
        near_due_orders = (
            db_session.query(SalesOrderLine, SalesOrder, Product)
            .join(SalesOrder, SalesOrder.id == SalesOrderLine.sales_order_id)
            .join(Product, Product.id == SalesOrderLine.product_id)
            .filter(
                SalesOrder.order_date <= as_of,
                SalesOrder.requested_delivery_date > as_of,
                SalesOrder.requested_delivery_date <= horizon_end,
                SalesOrder.status != "FULFILLED"
            )
            .all()
        )

        for so_line, so, prod in near_due_orders:
            p_id = str(so_line.product_id)
            p_snap = snapshot.get("products", {}).get(p_id, {})
            current_fg = float(p_snap.get("fg_stock", 0.0))
            planned_prod = float(p_snap.get("planned_production", 0.0))
            projected_avail = current_fg + planned_prod

            pending = max(0, (so_line.quantity_ordered or 0) - (so_line.quantity_fulfilled or 0))
            if pending > 0:
                days_ahead = (so.requested_delivery_date - as_of).days
                if projected_avail < pending:
                    candidate_actions.append({
                        "rule": 2,
                        "so_id": so.id,
                        "action": f"At risk: Order SO-{so.id}",
                        "reason": f"Order SO-{so.id} ({prod.name}) due in {days_ahead} days ({pending} units) exceeds projected availability of {int(projected_avail)} units",
                        "role": "Planner",
                        "target_due": so.requested_delivery_date.isoformat(),
                        "severity_weight": 20.0 + pending
                    })
                else:
                    # Healthy buffer, good candidate for watchlist if cushion is thin
                    if projected_avail - pending <= 10:
                        watchlist_candidates.append({
                            "item": f"Tight buffer on SO-{so.id} ({prod.name})",
                            "reason": f"Order due {so.requested_delivery_date.isoformat()} has only {int(projected_avail - pending)} units cushion above planned fulfillment",
                            "role": "Planner"
                        })

        # ──────────────────────────────────────────────────────────────────────
        # Rule 3: Materials at or below safety stock or reorder point with no open PO
        # ──────────────────────────────────────────────────────────────────────
        for m_id, m_data in snapshot.get("materials", {}).items():
            stock = float(m_data["stock"])
            safety = float(m_data["safety_stock"])
            reorder = float(m_data["reorder_point"])
            open_pos = int(m_data["open_pos_count"])
            name = m_data["name"]

            if stock <= safety:
                candidate_actions.append({
                    "rule": 3,
                    "action": f"Expedite urgent replenishment for {name}",
                    "reason": f"{name} stock at {int(stock)} kg is at or below safety stock ({int(safety)} kg). Cover is {m_data['days_of_cover']} days",
                    "role": "Procurement",
                    "target_due": as_of.isoformat(),
                    "severity_weight": 30.0 + (safety - stock)
                })
            elif stock <= reorder and open_pos == 0:
                candidate_actions.append({
                    "rule": 3,
                    "action": f"Reorder {name}",
                    "reason": f"{name} stock at {int(stock)} kg is at or below reorder point ({int(reorder)} kg) with 0 open purchase orders",
                    "role": "Procurement",
                    "target_due": as_of.isoformat(),
                    "severity_weight": 15.0
                })
            elif stock <= reorder and open_pos > 0:
                watchlist_candidates.append({
                    "item": f"{name} inventory monitoring",
                    "reason": f"{name} is at {int(stock)} kg (below reorder point {int(reorder)} kg), tracking {open_pos} open replenishment POs",
                    "role": "Procurement"
                })

        # ──────────────────────────────────────────────────────────────────────
        # Rule 4: Open POs overdue (rank by days overdue)
        # ──────────────────────────────────────────────────────────────────────
        for m_id, m_data in snapshot.get("materials", {}).items():
            for po_entry in m_data.get("overdue_pos", []):
                days_over = po_entry["days_overdue"]
                candidate_actions.append({
                    "rule": 4,
                    "po_id": po_entry["po_id"],
                    "days_overdue": days_over,
                    "action": f"Chase supplier {po_entry['supplier_name']} (PO-{po_entry['po_id']})",
                    "reason": f"PO-{po_entry['po_id']} for {m_data['name']} ({po_entry['pending_quantity']} units) is {days_over} days overdue from {po_entry['supplier_name']}",
                    "role": "Procurement",
                    "target_due": as_of.isoformat(),
                    "severity_weight": 10.0 + (days_over * 2.0)
                })

        # ──────────────────────────────────────────────────────────────────────
        # Rule 5: Yesterday's production shortfall with a capacity cause
        # ──────────────────────────────────────────────────────────────────────
        for p_id, p_data in snapshot.get("products", {}).items():
            shortfall = int(p_data.get("production_shortfall", 0))
            if shortfall > 0:
                candidate_actions.append({
                    "rule": 5,
                    "product_id": p_id,
                    "action": f"Review capacity & throughput for {p_data['name']}",
                    "reason": f"{p_data['name']} manufactured {p_data['actual_production']} units vs {p_data['planned_production']} planned ({shortfall} units shortfall)",
                    "role": "Plant Manager",
                    "target_due": as_of.isoformat(),
                    "severity_weight": 5.0 + shortfall
                })

        # ──────────────────────────────────────────────────────────────────────
        # Select Top 5 by Rule Hierarchy (Rule 1 -> 2 -> 3 -> 4 -> 5)
        # ──────────────────────────────────────────────────────────────────────
        candidate_actions.sort(key=lambda x: (x["rule"], -x.get("days_overdue", 0), -x.get("severity_weight", 0)))

        top_5: List[Dict[str, Any]] = []
        for idx, act in enumerate(candidate_actions[:5], start=1):
            top_5.append({
                "rank": idx,
                "action": act["action"],
                "reason": act["reason"],
                "role": act["role"],
                "due_date": act["target_due"],
                "rule_tier": act["rule"]
            })

        # If fewer than 5 actions, add nominal planned maintenance/audit items
        if len(top_5) < 5:
            nominal_defaults = [
                {
                    "action": "Audit master production schedule targets",
                    "reason": "Verify scheduled workcenter batches against weekly sales order forecasts",
                    "role": "Planner",
                    "due_date": as_of.isoformat()
                },
                {
                    "action": "Review supplier on-time delivery scorecards",
                    "reason": "Confirm upcoming replenishment deliveries remain on schedule",
                    "role": "Procurement",
                    "due_date": as_of.isoformat()
                },
                {
                    "action": "Routine workcenter equipment calibration",
                    "reason": "Standard preventative maintenance on primary motor assembly lines",
                    "role": "Plant Manager",
                    "due_date": as_of.isoformat()
                },
                {
                    "action": "Safety stock verification audit",
                    "reason": "Validate physical inventory cycle counts against ERP closing stock balances",
                    "role": "Planner",
                    "due_date": as_of.isoformat()
                },
                {
                    "action": "Monitor raw material warehouse receipts",
                    "reason": "Ensure dock reception procedures meet standard 24-hour turnaround",
                    "role": "Procurement",
                    "due_date": as_of.isoformat()
                }
            ]
            for default_act in nominal_defaults:
                if len(top_5) >= 5:
                    break
                top_5.append({
                    "rank": len(top_5) + 1,
                    "action": default_act["action"],
                    "reason": default_act["reason"],
                    "role": default_act["role"],
                    "due_date": default_act["due_date"],
                    "rule_tier": 0
                })

        # Watch-list: Up to 3 items from remaining candidates or watchlist items
        watchlist: List[Dict[str, Any]] = []
        # First use excess action candidates
        for extra in candidate_actions[5:]:
            if len(watchlist) >= 3:
                break
            watchlist.append({
                "item": extra["action"],
                "reason": extra["reason"],
                "role": extra["role"]
            })

        # Then use watchlist candidates
        for w in watchlist_candidates:
            if len(watchlist) >= 3:
                break
            if not any(x["item"] == w["item"] for x in watchlist):
                watchlist.append(w)

        # If still empty, add calm status
        if not watchlist:
            watchlist.append({
                "item": "Finished goods warehouse stock health",
                "reason": "All finished goods buffers maintained within healthy operating margins",
                "role": "Planner"
            })
            watchlist.append({
                "item": "Inbound supplier dispatch lead times",
                "reason": "Vendor shipment intervals tracking within nominal purchase order parameters",
                "role": "Procurement"
            })

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

        # Save to analytics/priorities/priorities_<as_of>.json
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
    print("\n--- TOP 5 PRIORITIES ---")
    for p in res["top_priorities"]:
        print(f"[{p['rank']}] {p['action']} ({p['role']}) -> {p['reason']}")
    print("\n--- WATCHLIST ---")
    for w in res["watchlist"]:
        print(f"• {w['item']} -> {w['reason']}")
