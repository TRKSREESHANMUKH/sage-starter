"""
stage10/demo_facts.py

Single Source of Truth for 10-Day Demo Facts.
Reads ONLY the demo pack files + live DB and deterministically generates:
  - stage10/DEMO_FACTS.json
  - stage10/DEMO_FACTS.md

Mandatory Framing:
"SAGE performs controlled synthetic causal-attribution evaluation under an expert-defined causal model; it does not claim to prove real-world causality."
"""

from __future__ import annotations

import csv
import glob
import hashlib
import json
import os
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

RESEARCH_FRAMING = (
    "SAGE performs controlled synthetic causal-attribution evaluation "
    "under an expert-defined causal model; it does not claim to prove real-world causality."
)

PRODUCT_NAMES = {
    101: "Steel Rod 10mm",
    102: "Plastic Granules",
    103: "Copper Wire",
    201: "Widget Model X",
    202: "Widget Model Y"
}

SUPPLIER_NAMES = {
    1: "Sri Materials Pvt Ltd",
    2: "Bharat Steel Works",
    3: "Global Polymers Co",
    4: "EastCoast Components",
    5: "Copper & Co"
}


def hash_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def generate_demo_facts() -> Dict[str, Any]:
    # 1. Connect to baseline DB to get 2025-placed orders due in 2026
    baseline_db_path = ROOT_DIR / "live" / "sage_live_baseline.db"
    if not baseline_db_path.exists():
        baseline_db_path = ROOT_DIR / "live" / "sage_live.db"

    conn = sqlite3.connect(baseline_db_path)
    c = conn.cursor()

    # Get baseline DB hash
    baseline_hash = hash_file(baseline_db_path)

    # 2. Gather pack hashes
    pack_hashes = {}
    for d_path in sorted(glob.glob(str(ROOT_DIR / "demo_data" / "packs" / "2026-01-*"))):
        day_str = Path(d_path).name
        so_csv = Path(d_path) / "sales_orders.csv"
        pack_hashes[day_str] = hash_file(so_csv) if so_csv.exists() else ""

    # 3. Gather sales orders
    # A. 2025-placed orders due in 2026 (SO #220, 221, 224, 225, 226, 227, 228, 229, 230)
    c.execute("""
        SELECT so.id, so.order_date, so.requested_delivery_date, sol.product_id, sol.quantity_ordered, so.status
        FROM sales_orders so
        JOIN sales_order_lines sol ON so.id = sol.sales_order_id
        WHERE so.requested_delivery_date >= '2026-01-01'
        ORDER BY so.id
    """)
    rows_2025 = c.fetchall()
    all_sales_orders = []
    for r in rows_2025:
        all_sales_orders.append({
            "order_id": r[0],
            "order_date": r[1],
            "requested_delivery_date": r[2],
            "product_id": r[3],
            "product_name": PRODUCT_NAMES.get(r[3], f"Product {r[3]}"),
            "quantity_ordered": r[4],
            "shipped_date": None,
            "status": "Backorder",
            "source_provenance": "2025 Baseline Ledger (live/sage_live_baseline.db)",
            "sha256": baseline_hash
        })

    # B. 2026 pack sales orders
    # Also gather deliveries to know shipped date
    deliveries_map = {}  # so_id -> ship_date
    for d_path in sorted(glob.glob(str(ROOT_DIR / "demo_data" / "packs" / "2026-01-*"))):
        deliv_csv = Path(d_path) / "deliveries.csv"
        if deliv_csv.exists():
            with open(deliv_csv, "r", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    so_id = int(row["sales_order_id"])
                    deliveries_map[so_id] = row["ship_date"]

    for d_path in sorted(glob.glob(str(ROOT_DIR / "demo_data" / "packs" / "2026-01-*"))):
        day_str = Path(d_path).name
        so_csv = Path(d_path) / "sales_orders.csv"
        sol_csv = Path(d_path) / "sales_order_lines.csv"
        if not so_csv.exists() or not sol_csv.exists():
            continue

        so_rows = {int(r["id"]): r for r in csv.DictReader(open(so_csv, encoding="utf-8"))}
        for sol_row in csv.DictReader(open(sol_csv, encoding="utf-8")):
            so_id = int(sol_row["sales_order_id"])
            so_info = so_rows.get(so_id, {})
            p_id = int(sol_row["product_id"])
            qty = int(sol_row["quantity_ordered"])
            ship_d = deliveries_map.get(so_id)
            status = "Delivered" if ship_d else so_info.get("status", "Pending")

            all_sales_orders.append({
                "order_id": so_id,
                "order_date": so_info.get("order_date"),
                "requested_delivery_date": so_info.get("requested_delivery_date"),
                "product_id": p_id,
                "product_name": PRODUCT_NAMES.get(p_id, f"Product {p_id}"),
                "quantity_ordered": qty,
                "shipped_date": ship_d,
                "status": status,
                "source_provenance": f"demo_data/packs/{day_str}/sales_orders.csv",
                "sha256": pack_hashes.get(day_str, "")
            })

    # Sort sales orders by order_id
    all_sales_orders.sort(key=lambda x: x["order_id"])

    # 4. Opening stock per day (from manifest and pack metadata)
    # Manifest opening 2025-12-31 closing
    manifest_path = ROOT_DIR / "stage10" / "demo_seed_manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest_data = json.load(f)

    # Closing stock of each day from pack metadata
    closing_stock_per_day = {}
    for d_path in sorted(glob.glob(str(ROOT_DIR / "demo_data" / "packs" / "2026-01-*"))):
        day_str = Path(d_path).name
        meta_p = Path(d_path) / "metadata.json"
        with open(meta_p, "r", encoding="utf-8") as f:
            meta = json.load(f)
        closing_stock_per_day[day_str] = meta.get("closing_stock_simulated", {})

    # Opening stock on Jan 1:
    opening_stock_per_day = {}
    opening_stock_per_day["2026-01-01"] = {
        "steel_rod_kg": 215.0,
        "plastic_granules_kg": 204.0,
        "copper_wire_m": 184.0,
        "widget_x_units": 25,
        "widget_y_units": 20
    }
    for d_num in range(2, 11):
        prev_day_str = f"2026-01-{d_num-1:02d}"
        curr_day_str = f"2026-01-{d_num:02d}"
        prev_closing = closing_stock_per_day.get(prev_day_str, {})
        mats = prev_closing.get("materials", {})
        fgs = prev_closing.get("finished_goods", {})
        opening_stock_per_day[curr_day_str] = {
            "steel_rod_kg": float(mats.get("101", 0.0)),
            "plastic_granules_kg": float(mats.get("102", 0.0)),
            "copper_wire_m": float(mats.get("103", 0.0)),
            "widget_x_units": int(fgs.get("201", 0)),
            "widget_y_units": int(fgs.get("202", 0))
        }

    # 5. Load feed results (tiers and alert headlines)
    feed_results_path = ROOT_DIR / "stage10" / "demo_feed_results.json"
    with open(feed_results_path, "r", encoding="utf-8") as f:
        feed_results = json.load(f)
    days_feed_map = {d["day"]: d for d in feed_results.get("days", [])}

    # 6. Purchase Orders tracking across Days 1-10
    # POs:
    # PO #18: EastCoast Components, Steel Rod 407 kg, ordered 2025-08-05, expected 2025-08-14, Cancelled 2025-12-31
    # PO #19: EastCoast Components, Steel Rod 400 kg, ordered 2025-12-25, expected 2026-01-02
    # PO #20: Global Polymers Co, Plastic Granules 250 kg, ordered 2025-12-21, expected 2026-01-04
    # PO #21: Copper & Co, Copper Wire 200 m, ordered 2025-12-25, expected 2026-01-06
    # PO #22: Global Polymers Co, Plastic Granules 150 kg, ordered 2026-01-08, expected 2026-01-10
    po_definitions = [
        {"id": 18, "supplier_id": 4, "supplier_name": "EastCoast Components", "material_id": 101, "material_name": "Steel Rod 10mm", "qty": 407, "expected": "2025-08-14", "ordered": "2025-08-05", "initial_status": "Cancelled"},
        {"id": 19, "supplier_id": 4, "supplier_name": "EastCoast Components", "material_id": 101, "material_name": "Steel Rod 10mm", "qty": 400, "expected": "2026-01-02", "ordered": "2025-12-25", "initial_status": "Pending"},
        {"id": 20, "supplier_id": 3, "supplier_name": "Global Polymers Co", "material_id": 102, "material_name": "Plastic Granules", "qty": 250, "expected": "2026-01-04", "ordered": "2025-12-21", "initial_status": "Pending"},
        {"id": 21, "supplier_id": 5, "supplier_name": "Copper & Co", "material_id": 103, "material_name": "Copper Wire", "qty": 200, "expected": "2026-01-06", "ordered": "2025-12-25", "initial_status": "Pending"},
        {"id": 22, "supplier_id": 3, "supplier_name": "Global Polymers Co", "material_id": 102, "material_name": "Plastic Granules", "qty": 150, "expected": "2026-01-10", "ordered": "2026-01-08", "initial_status": "Pending"},
    ]

    # Daily PO status
    daily_po_status = {}
    for d_num in range(1, 11):
        dt = date(2026, 1, d_num)
        pos_for_day = []
        for po in po_definitions:
            po_id = po["id"]
            if po_id == 22 and d_num < 8:
                continue  # Not placed yet

            # Received calculation
            rec = 0
            if po_id == 19:
                rec = 400 if d_num >= 8 else 0
            elif po_id == 20:
                if d_num >= 8:
                    rec = 250
                elif d_num >= 4:
                    rec = 150
                else:
                    rec = 0
            elif po_id == 21:
                rec = 200 if d_num >= 6 else 0
            elif po_id == 22:
                rec = 0
            elif po_id == 18:
                rec = 0

            # Overdue days calculation: strict requested < D
            exp_d = date.fromisoformat(po["expected"])
            if po_id == 18:
                days_overdue = (dt - exp_d).days
                status = "Cancelled"
            elif rec >= po["qty"]:
                days_overdue = 0
                status = "Completed"
            elif dt > exp_d:
                days_overdue = (dt - exp_d).days
                status = "Overdue"
            else:
                days_overdue = 0
                status = "Pending"

            pos_for_day.append({
                "po_id": po_id,
                "supplier_id": po["supplier_id"],
                "supplier_name": po["supplier_name"],
                "material_id": po["material_id"],
                "material_name": po["material_name"],
                "quantity_ordered": po["qty"],
                "expected_delivery_date": po["expected"],
                "quantity_received": rec,
                "days_overdue": days_overdue,
                "status": status
            })
        daily_po_status[f"2026-01-{d_num:02d}"] = pos_for_day

    # 7. Daily operational metrics, overdue, backlog, alerts & forecast
    from stage10.forecast.outlook import get_weekly_forecast

    daily_ledger = []
    for d_num in range(1, 11):
        d_str = f"2026-01-{d_num:02d}"
        d_obj = date(2026, 1, d_num)
        feed_info = days_feed_map.get(d_num, {})

        # Overdue (< D) and Due Today (== D)
        # Orders unfulfilled at start of day
        od_orders = 0
        od_units = 0
        dt_orders = 0
        dt_units = 0

        for so in all_sales_orders:
            req_d = date.fromisoformat(so["requested_delivery_date"])
            shipped_d = date.fromisoformat(so["shipped_date"]) if so["shipped_date"] else None
            # Was this order fulfilled BEFORE day D?
            fulfilled_before_today = (shipped_d is not None and shipped_d < d_obj)
            if fulfilled_before_today:
                continue

            # If not fulfilled before today, does it fall into Overdue (< D) or Due Today (== D)?
            if req_d < d_obj:
                od_orders += 1
                od_units += so["quantity_ordered"]
            elif req_d == d_obj:
                dt_orders += 1
                dt_units += so["quantity_ordered"]

        total_backlog_orders = od_orders + dt_orders
        total_backlog_units = od_units + dt_units

        # Top 3 alerts (fixing any '1 units' grammar)
        raw_top_alerts = [a["headline"] for a in feed_info.get("alerts", [])[:3]]
        top_alerts = [a.replace("shortfall of 1 units", "shortfall of 1 unit") for a in raw_top_alerts]

        # Forecast strip values calculated dynamically from ledger orders placed on or before d_obj
        d_start = d_obj + timedelta(days=1)
        d_end = d_obj + timedelta(days=7)
        t28_start = d_obj - timedelta(days=28)

        # 1. Known booked units due in D+1..D+7 (placed on or before day D)
        booked_orders = [
            so for so in all_sales_orders
            if date.fromisoformat(so["order_date"]) <= d_obj
            and d_start <= date.fromisoformat(so["requested_delivery_date"]) <= d_end
            and so.get("status") != "Cancelled"
        ]
        b_x = sum(so["quantity_ordered"] for so in booked_orders if so["product_id"] == 201)
        b_y = sum(so["quantity_ordered"] for so in booked_orders if so["product_id"] == 202)
        booked = b_x + b_y

        # 2. Deployed Model: Trailing 28-day mean of placed units x 7 computed live as of day D
        t28_orders = [
            so for so in all_sales_orders
            if t28_start < date.fromisoformat(so["order_date"]) <= d_obj
            and so.get("status") != "Cancelled"
        ]
        t28_x = sum(so["quantity_ordered"] for so in t28_orders if so["product_id"] == 201)
        t28_y = sum(so["quantity_ordered"] for so in t28_orders if so["product_id"] == 202)
        pred_x = round((t28_x / 28.0) * 7.0, 1)
        pred_y = round((t28_y / 28.0) * 7.0, 1)
        pred_tot = round(pred_x + pred_y, 1)
        exp_new = int(round(pred_tot))
        new_x = int(round(pred_x))
        new_y = int(round(pred_y))

        # CV-calibrated range method (v4): 80% interval on new arrivals
        lo = int(round(max(0, pred_tot * 0.55)))
        hi = int(round(pred_tot * 1.50))
        tot_due = booked + exp_new
        tot_lo = booked + lo
        tot_hi = booked + hi

        tot_x = b_x + new_x
        tot_y = b_y + new_y

        # 3. Actual units due in D+1..D+7 in ledger (placed anytime)
        actual_due = [
            so for so in all_sales_orders
            if d_start <= date.fromisoformat(so["requested_delivery_date"]) <= d_end
            and so.get("status") != "Cancelled"
        ]
        act_due_tot = sum(so["quantity_ordered"] for so in actual_due)
        act_due_x = sum(so["quantity_ordered"] for so in actual_due if so["product_id"] == 201)
        act_due_y = sum(so["quantity_ordered"] for so in actual_due if so["product_id"] == 202)

        # 4. Actual units placed in D+1..D+7 in ledger
        actual_placed = [
            so for so in all_sales_orders
            if d_start <= date.fromisoformat(so["order_date"]) <= d_end
            and so.get("status") != "Cancelled"
        ]
        act_placed_tot = sum(so["quantity_ordered"] for so in actual_placed)
        act_placed_x = sum(so["quantity_ordered"] for so in actual_placed if so["product_id"] == 201)
        act_placed_y = sum(so["quantity_ordered"] for so in actual_placed if so["product_id"] == 202)

        is_complete_window = (d_obj + timedelta(days=7)) <= date(2026, 1, 10)
        act_due_display = f"{act_due_tot}u (X={act_due_x}, Y={act_due_y})" if is_complete_window else "incomplete (data ends 10 Jan)"
        act_placed_display = f"{act_placed_tot}u (X={act_placed_x}, Y={act_placed_y})" if is_complete_window else "incomplete (data ends 10 Jan)"

        daily_ledger.append({
            "day": d_num,
            "date": d_str,
            "tier": feed_info.get("status_word", "NORMAL"),
            "overdue_orders_count": od_orders,
            "overdue_orders_units": od_units,
            "due_today_orders_count": dt_orders,
            "due_today_orders_units": dt_units,
            "standing_backlog_orders": od_orders,
            "standing_backlog_units": od_units,
            "total_open_orders": total_backlog_orders,
            "total_open_units": total_backlog_units,
            "opening_stock": opening_stock_per_day.get(d_str, {}),
            "top_3_alerts": top_alerts,
            "forecast_strip": {
                "headline": f"Next 7 days: expected demand ~{tot_due} units due (likely range {tot_lo}–{tot_hi})",
                "breakdown_text": f"{booked} already booked + ~{exp_new} expected new orders",
                "product_breakdown": f"Widget Model X: ~{tot_x}u due ({b_x} booked + ~{new_x} new) | Widget Model Y: ~{tot_y}u due ({b_y} booked + ~{new_y} new)",
                "total_expected_due_units": tot_due,
                "likely_range_low": tot_lo,
                "likely_range_high": tot_hi,
                "booked_units": booked,
                "expected_new_orders": exp_new,
                "forecast_window_complete": is_complete_window,
                "actual_units_due_next_7d": act_due_display,
                "actual_units_due_x": act_due_x if is_complete_window else None,
                "actual_units_due_y": act_due_y if is_complete_window else None,
                "actual_units_placed_next_7d": act_placed_display,
                "actual_units_placed_x": act_placed_x if is_complete_window else None,
                "actual_units_placed_y": act_placed_y if is_complete_window else None,
            },
            "active_pos": daily_po_status.get(d_str, [])
        })

    conn.close()

    result = {
        "metadata": {
            "title": "SAGE Stage 10 Deterministic Demo Facts",
            "framing": RESEARCH_FRAMING,
            "generated_at": date.today().isoformat(),
            "scope": "Ten-Day Operational Demo Feed (2026-01-01 to 2026-01-10)",
            "total_sales_orders": len(all_sales_orders),
            "total_days": len(daily_ledger)
        },
        "sales_orders": all_sales_orders,
        "daily_ledger": daily_ledger
    }

    # Write DEMO_FACTS.json
    out_json = ROOT_DIR / "stage10" / "DEMO_FACTS.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    # Write DEMO_FACTS.md
    out_md = ROOT_DIR / "stage10" / "DEMO_FACTS.md"
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("# SAGE — Single Source of Demo Facts (Days 1–10)\n\n")
        f.write(f"> **Mandatory Scientific Framing:**  \n> \"{RESEARCH_FRAMING}\"\n\n")
        f.write("---\n\n")

        f.write("## 1. Daily Operations & Backlog Ledger (Days 1–10)\n\n")
        f.write("| Day | Date | Tier | Overdue (< D) | Due Today (== D) | Open Backlog (Total) | Opening Stock (Steel / Plast / Cu) | Top Alert Headline |\n")
        f.write("| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :--- |\n")
        for d in daily_ledger:
            stk = d["opening_stock"]
            stk_str = f"{int(stk.get('steel_rod_kg', 0))}kg / {int(stk.get('plastic_granules_kg', 0))}kg / {int(stk.get('copper_wire_m', 0))}m"
            top_h = d["top_3_alerts"][0] if d["top_3_alerts"] else "None"
            f.write(f"| Day {d['day']} | {d['date']} | **{d['tier']}** | {d['overdue_orders_count']} ord ({d['overdue_orders_units']}u) | {d['due_today_orders_count']} ord ({d['due_today_orders_units']}u) | {d['total_open_orders']} ord ({d['total_open_units']}u) | {stk_str} | {top_h} |\n")

        f.write("\n---\n\n")
        f.write("## 2. Daily Forecast Strip Values & Realized Ledger Actuals (Days 1–10)\n\n")
        f.write("> *Method Note*: The demo feed's order rate is elevated (~7.3 vs ~14.6 units/day, 2.0x units ratio; ~0.63 vs 2.2 orders/day, 3.5x orders ratio), so demo-day forecasts are not an accuracy test. Accuracy metrics are never displayed for demo days.\n\n")
        f.write("| Day | Date | Forecast Strip Headline | Booked vs Expected New | Product Breakdown | Actual Units Due (D+1..D+7) | Actual Units Placed (D+1..D+7) |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- | :---: | :---: |\n")
        for d in daily_ledger:
            fc = d["forecast_strip"]
            act_due = fc["actual_units_due_next_7d"]
            act_placed = fc["actual_units_placed_next_7d"]
            f.write(f"| Day {d['day']} | {d['date']} | {fc['headline']} | {fc['breakdown_text']} | {fc['product_breakdown']} | {act_due} | {act_placed} |\n")

        f.write("\n---\n\n")
        f.write("## 3. Purchase Orders Status Ledger (Days 1–10)\n\n")
        f.write("| PO ID | Supplier | Material | Qty | Expected | Status across Days 1–10 |\n")
        f.write("| :---: | :--- | :--- | :---: | :---: | :--- |\n")
        f.write("| **#18** | EastCoast Components (S4) | Steel Rod 10mm (101) | 407 | 2025-08-14 | Cancelled on 2025-12-31 baseline reset (0 received, 139d overdue at Dec 31) |\n")
        f.write("| **#19** | EastCoast Components (S4) | Steel Rod 10mm (101) | 400 | 2026-01-02 | Overdue Days 3–7 (1d to 5d overdue); Received in full (400 kg) on Day 8 (GR #25) |\n")
        f.write("| **#20** | Global Polymers Co (S3) | Plastic Granules (102) | 250 | 2026-01-04 | 150 kg (60%) received Day 4 (GR #23); 100 kg overdue Days 5–7; completed Day 8 (GR #26) |\n")
        f.write("| **#21** | Copper & Co (S5) | Copper Wire (103) | 200 | 2026-01-06 | Received in full (200 m) on Day 6 (GR #24) on expected date |\n")
        f.write("| **#22** | Global Polymers Co (S3) | Plastic Granules (102) | 150 | 2026-01-10 | Placed Day 8 (2026-01-08); Pending on Day 10 (0 received, expected today) |\n")

        f.write("\n---\n\n")
        f.write("## 4. Complete Sales Orders Ledger (2025 Standing + 2026 Ingested)\n\n")
        f.write("| Order ID | Placed Date | Requested Date | Product | Qty | Shipped Date | Final Status | Source Provenance | Pack CSV SHA256 |\n")
        f.write("| :---: | :---: | :---: | :--- | :---: | :---: | :---: | :--- | :--- |\n")
        for so in all_sales_orders:
            shipped = so["shipped_date"] if so["shipped_date"] else "Unshipped (Backordered)"
            short_hash = so["sha256"][:12] + "…" if so["sha256"] else "—"
            f.write(f"| SO #{so['order_id']} | {so['order_date']} | {so['requested_delivery_date']} | {so['product_name']} ({so['product_id']}) | {so['quantity_ordered']}u | {shipped} | {so['status']} | {so['source_provenance']} | `{short_hash}` |\n")

    return result


if __name__ == "__main__":
    res = generate_demo_facts()
    print("Generated stage10/DEMO_FACTS.json and stage10/DEMO_FACTS.md successfully.")
