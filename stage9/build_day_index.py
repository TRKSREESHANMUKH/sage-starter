"""
stage9/build_day_index.py — Persistent Day Index Builder for SAGE.

Computes and maintains stage9/state/day_index.json through the normal product pipeline:
  - as_of date (from 2025-01-01 to current_day)
  - banner_tier: "Normal", "Watch", "Needs attention", "Critical"
  - issue_count: int
  - top_alert_headline: str
  - top_alert_trigger: str
  - top_alert_evidence: str
  - event flags (stockout, partial_receipt, overdue_po, shortfall, demand_surge)

Strict zero look-ahead: Day D is evaluated using only facts <= D.
Never uses incident labels or answer key.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from stage9.current_day import get_current_day
from stage9.snapshot import compute_daily_snapshot, load_rules
from app.database import SessionLocal

DAY_INDEX_PATH = ROOT_DIR / "stage9" / "state" / "day_index.json"


def derive_day_entry(as_of: date, snap: Dict[str, Any]) -> Dict[str, Any]:
    sev = snap.get("plant_severity", "NORMAL")
    if sev == "CRITICAL":
        banner_tier = "Critical"
    elif sev == "NEEDS_ATTENTION":
        banner_tier = "Needs attention"
    elif sev == "WATCH":
        banner_tier = "Watch"
    else:
        banner_tier = "Normal"

    # Inspect operational signals directly from snapshot
    kpis = snap.get("kpis", {})
    mats = snap.get("materials", {})
    prods = snap.get("products", {})
    receipts = snap.get("receipts_today", [])

    has_stockout = any(float(m.get("stock", 100.0)) <= 0.0 for m in mats.values())
    has_overdue_po = any(len(m.get("overdue_pos", [])) > 0 for m in mats.values())
    has_partial_receipt = any(r.get("fill_rate", 1.0) < 1.0 for r in receipts)
    has_shortfall = any(p.get("production_shortfall", 0) > 0 for p in prods.values())
    has_demand_surge = any(p.get("demand_units", 0) >= 10 for p in prods.values())
    backlog_units = int(kpis.get("total_backlog_units", 0))

    # Derive headline and trigger strictly from operational pipeline
    headline = "Normal operations across all monitored workcenters"
    trigger = "All parameters within normal operating thresholds"
    evidence = "Seen end to end"
    issue_count = 0

    if has_stockout:
        issue_count += 1
        m_stockout = [m["name"] for m in mats.values() if float(m.get("stock", 100.0)) <= 0.0]
        m_name = m_stockout[0] if m_stockout else "Raw Material"
        u_label = "meters" if "Copper" in m_name else "kg"
        headline = f"Raw material stockout on {m_name} (0 {u_label} in stock)"
        trigger = "Inventory depleted to 0 units; assembly line halted"
        evidence = "Seen end to end"
    elif has_overdue_po:
        issue_count += 1
        overdue_list = [p for m in mats.values() for p in m.get("overdue_pos", [])]
        top_po = overdue_list[0] if overdue_list else {}
        supp_name = top_po.get("supplier_name", "Supplier")
        po_id = top_po.get("po_id", "")
        days_late = top_po.get("days_overdue", 1)
        headline = f"Overdue delivery from {supp_name} (PO #{po_id})"
        trigger = f"Purchase order {days_late} days overdue beyond committed date"
        evidence = "Seen end to end"
    elif backlog_units > 0:
        issue_count += 1
        late_orders = int(kpis.get("total_overdue_orders", 0))
        yest_backlog = int(kpis.get("yest_backlog_units", 0))
        if yest_backlog > 0 and backlog_units < yest_backlog:
            headline = f"Standing customer backlog clearing ({late_orders} orders, {backlog_units} units)"
            trigger = f"{backlog_units} units in customer backlog awaiting fulfillment (burning down)"
        else:
            headline = f"Standing customer backlog ({late_orders} orders, {backlog_units} units)"
            trigger = f"{backlog_units} units in customer backlog awaiting fulfillment"
        evidence = "Seen end to end"
    elif has_shortfall:
        issue_count += 1
        sf_prods = [p for p in prods.values() if p.get("production_shortfall", 0) > 0]
        top_p = sf_prods[0] if sf_prods else {}
        p_name = top_p.get("name", "Product")
        sf_qty = top_p.get("production_shortfall", 0)
        u_sf = "unit" if sf_qty == 1 else "units"
        headline = f"Production below plan ({p_name} shortfall of {sf_qty} {u_sf})"
        trigger = f"Workcenter shift output completed {sf_qty} {u_sf} below scheduled plan"
        evidence = "Partly seen"
    elif has_partial_receipt:
        issue_count += 1
        pr = [r for r in receipts if r.get("fill_rate", 1.0) < 1.0][0]
        supp_name = pr.get("supplier_name", "Supplier")
        po_id = pr.get("po_id", pr.get("receipt_id", ""))
        fill_pct = int(pr.get("fill_rate", 0) * 100)
        headline = f"Partial delivery from {supp_name} (PO #{po_id})"
        trigger = f"Supplier delivered partial shipment ({fill_pct}% fill rate)"
        evidence = "Seen end to end"
    elif has_demand_surge:
        issue_count += 1
        dem_p = [p for p in prods.values() if p.get("demand_units", 0) >= 10][0]
        p_name = dem_p.get("name", "Product")
        d_qty = dem_p.get("demand_units", 0)
        headline = f"Elevated demand intake ({p_name} surge of {d_qty} units)"
        trigger = f"Customer demand volume reached {d_qty} units, absorbed by buffer"
        evidence = "Seen end to end"

    # Count additional issues
    if has_overdue_po and has_stockout:
        issue_count += 1
    if has_shortfall and (has_stockout or has_overdue_po):
        issue_count += 1
    if has_partial_receipt and (has_stockout or has_overdue_po):
        issue_count += 1

    return {
        "date": as_of.isoformat(),
        "banner_tier": banner_tier,
        "issue_count": issue_count,
        "top_alert_headline": headline,
        "top_alert_trigger": trigger,
        "top_alert_evidence": evidence,
        "signals": {
            "has_stockout": has_stockout,
            "has_overdue_po": has_overdue_po,
            "has_partial_receipt": has_partial_receipt,
            "has_shortfall": has_shortfall,
            "has_demand_surge": has_demand_surge,
            "backlog_units": backlog_units
        }
    }


def build_day_index(
    start_date: date = date(2025, 1, 1),
    end_date: Optional[date] = None,
    progress_callback=None
) -> Dict[str, Any]:
    """
    Builds or updates stage9/state/day_index.json from start_date to end_date.
    Uses existing index if available to do incremental updates.
    """
    DAY_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    if end_date is None:
        end_date = get_current_day()

    index_data: Dict[str, Any] = {}
    if DAY_INDEX_PATH.exists():
        try:
            with open(DAY_INDEX_PATH, "r", encoding="utf-8") as f:
                index_data = json.load(f).get("days", {})
        except Exception:
            index_data = {}

    db_main = SessionLocal(source="main")
    db_live = SessionLocal(source="live")

    curr = start_date
    all_dates = []
    while curr <= end_date:
        all_dates.append(curr)
        curr += timedelta(days=1)

    t0 = time.time()
    total = len(all_dates)

    try:
        for idx, d in enumerate(all_dates):
            d_str = d.isoformat()
            # Reuse cached entry if before current_day and already present
            if d_str in index_data and d < end_date:
                continue

            src = "live" if d.year >= 2026 else "main"
            sess = db_live if src == "live" else db_main

            snap = compute_daily_snapshot(d, db_session=sess, source=src)
            entry = derive_day_entry(d, snap)
            index_data[d_str] = entry

            if progress_callback and (idx % 25 == 0 or idx == total - 1):
                progress_callback(idx + 1, total, d_str)
    finally:
        db_main.close()
        db_live.close()

    elapsed = round(time.time() - t0, 2)
    payload = {
        "metadata": {
            "last_built": date.today().isoformat(),
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "total_days": len(index_data),
            "build_elapsed_seconds": elapsed,
            "framing": "SAGE performs controlled synthetic causal-attribution evaluation under an expert-defined causal model; it does not claim to prove real-world causality."
        },
        "days": index_data
    }

    with open(DAY_INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    return payload


def get_episodes(day_index: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Groups consecutive non-normal days into episodes, plus single-day notable events.
    Strictly derived from daily status; never from incident labels.
    """
    days_dict = day_index.get("days", {}) if "days" in day_index else day_index
    sorted_dates = sorted(days_dict.keys())

    episodes: List[Dict[str, Any]] = []
    current_ep: Optional[Dict[str, Any]] = None

    for d_str in sorted_dates:
        entry = days_dict[d_str]
        tier = entry["banner_tier"]
        sigs = entry.get("signals", {})

        is_disruption = tier in ("Critical", "Needs attention")

        if is_disruption:
            if current_ep is None:
                # Start new episode
                current_ep = {
                    "start_date": d_str,
                    "end_date": d_str,
                    "max_tier": tier,
                    "headline": entry["top_alert_headline"],
                    "evidence_label": entry["top_alert_evidence"],
                    "trigger": entry["top_alert_trigger"],
                    "days_count": 1,
                    "dates": [d_str]
                }
            else:
                # Extend episode
                current_ep["end_date"] = d_str
                current_ep["days_count"] += 1
                current_ep["dates"].append(d_str)
                if tier == "Critical" and current_ep["max_tier"] != "Critical":
                    current_ep["max_tier"] = "Critical"
                    current_ep["headline"] = entry["top_alert_headline"]
                    current_ep["trigger"] = entry["top_alert_trigger"]
        else:
            if current_ep is not None:
                episodes.append(current_ep)
                current_ep = None

            # Check single-day notable events during normal or watch tiers
            if sigs.get("has_demand_surge") or sigs.get("has_partial_receipt"):
                episodes.append({
                    "start_date": d_str,
                    "end_date": d_str,
                    "max_tier": tier,
                    "headline": entry["top_alert_headline"],
                    "evidence_label": entry["top_alert_evidence"],
                    "trigger": entry["top_alert_trigger"],
                    "days_count": 1,
                    "dates": [d_str]
                })

    if current_ep is not None:
        episodes.append(current_ep)

    return episodes


if __name__ == "__main__":
    print("Building day index for SAGE...")
    res = build_day_index(
        progress_callback=lambda cur, tot, d: print(f"Progress: {cur}/{tot} ({d})")
    )
    print(f"Built {res['metadata']['total_days']} days in {res['metadata']['build_elapsed_seconds']}s")
    eps = get_episodes(res["days"])
    print(f"Derived {len(eps)} key episodes.")
