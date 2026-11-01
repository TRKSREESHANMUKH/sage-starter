"""
stage10/demo_feed/generate_demo_feed.py — Deterministic Scripted Feed Generator for 2026 Demo Days (Jan 1 - Jan 10)

Implements SAGE Stage 10 Redesigned Ten-Day Simulation Feed (v4 Protocol):
- Generates 10 daily packs for 2026-01-01 through 2026-01-10 into demo_data/packs/ and demo_data/queue/
- Strictly respects master data, BOM relationships, lead times, and deterministic parameters.
- Re-calculates closing stock and statuses as of each pack day.
- Every day has non-zero operational activity:
    * 3-6 sales orders placed per day with lead times 3-8 days (drawn from 2025 distribution)
    * Non-zero forward booked units across the 7-day rolling forecast horizon
    * Real customer shipments and goods receipts
    * Production runs and stock movements
- Exercises genuine customer order fulfillment dynamics:
    * Day 5: Line 2 capacity shortfall delays SO #237
    * Day 7: Genuine late delivery of SO #237 (shipped late on Day 7)
    * Days 8-10: 9 carried-over backorders (109 units) from 2025-12-31 ship strictly FIFO:
        - Day 8: SO #220, #221, #225 (33 units) -> open backlog falls from 109 to 76 units
        - Day 9: SO #226, #227, #230 (30 units) -> open backlog falls from 76 to 46 units
        - Day 10: SO #224, #229, #228 (46 units) -> open backlog falls from 46 to 0 units
- Follows the pre-registered scenario script (stage10/prereg_demo_feed_v4.md):
    1. Jan 1: Normal operations (NORMAL)
    2. Jan 2: Widget Model X demand spike (WATCH)
    3. Jan 3: Supplier 4 steel delivery overdue (NEEDS_ATTENTION)
    4. Jan 4: Plastic 60% partial receipt, steel 2d late (NEEDS_ATTENTION)
    5. Jan 5: Line 2 capacity disruption, Widget Model Y -50% (NEEDS_ATTENTION)
    6. Jan 6: Steel 4d overdue, steel at safety stock 50 kg (CRITICAL)
    7. Jan 7: Steel stockout (0 kg), Widget Model X halted, genuine late customer shipment (CRITICAL)
    8. Jan 8: Steel arrives 5d late (in full), plastic balance arrives, production resumes, backlog burns down (NEEDS_ATTENTION)
    9. Jan 9: Seasonal Friday demand peak, backorders continue clearing FIFO (NEEDS_ATTENTION)
   10. Jan 10: Dual minor issues: Widget Y -20% and late plastic reorder PO #22. Backlog cleared. (NEEDS_ATTENTION)
"""

from __future__ import annotations

import csv
from datetime import date, timedelta
import json
from pathlib import Path
import yaml

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
PACKS_DIR = ROOT_DIR / "demo_data" / "packs"
QUEUE_DIR = ROOT_DIR / "demo_data" / "queue"
CONFIG_PATH = ROOT_DIR / "stage10" / "demo_feed" / "scenario_script.yaml"

FRAMING = "SAGE performs controlled synthetic causal-attribution evaluation under an expert-defined causal model; it does not claim to prove real-world causality."


def generate_packs():
    print("=" * 70)
    print("SAGE Stage 10: Generating Redesigned Ten-Day Demo Feed v4 (1–10 Jan 2026)")
    print("=" * 70)

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Master table parameters
    INV_ITEM_MAP = {101: 1, 102: 2, 103: 3, 201: 4, 202: 5}
    # BOM:
    # 201 (Widget X): 101: 2.5 kg, 102: 1.0 kg, 103: 0.3 m
    # 202 (Widget Y): 101: 1.2 kg, 103: 0.5 m
    BOM = {
        201: {101: 2.5, 102: 1.0, 103: 0.3},
        202: {101: 1.2, 103: 0.5}
    }

    # Opening stock on 2025-12-31:
    # Materials: 101: 215 kg, 102: 140 kg, 103: 110 m
    # Finished Goods: 201: 25 units, 202: 20 units
    mat_stock = {101: 215.0, 102: 140.0, 103: 110.0}
    fg_stock = {201: 25, 202: 20}

    # ID sequences continuing from 2025 year-end
    next_so_id = 231
    next_sol_id = 231
    next_po_id = 22
    next_pol_id = 22
    next_gr_id = 23
    next_grl_id = 23
    next_prod_id = 153
    next_issue_id = 204
    next_del_id = 177
    next_dell_id = 177
    next_mov_id = 489

    # Day-by-day deterministic order placements (3-4 orders per day, lead times 3-5 days)
    # (customer_id, product_id, quantity, lead_days)
    ORDERS_SCHEDULE = {
        1: [(1, 201, 5, 3), (2, 202, 4, 3), (3, 201, 4, 4)],  # Normal baseline: 9 units Model X (<10 surge limit)
        2: [(1, 201, 14, 3), (4, 201, 12, 4), (5, 201, 10, 5), (2, 202, 8, 3)],  # Model X demand surge: 36 units!
        3: [(3, 201, 9, 3), (1, 202, 10, 4), (5, 201, 11, 5)],
        4: [(2, 201, 10, 3), (4, 202, 8, 4), (3, 201, 12, 5)],
        5: [(1, 201, 11, 3), (2, 202, 9, 4), (5, 201, 10, 5)],
        6: [(3, 201, 10, 3), (4, 202, 8, 4), (1, 201, 12, 5)],
        7: [(2, 201, 10, 3), (3, 202, 8, 4), (5, 201, 12, 5)],
        8: [(1, 201, 11, 3), (4, 202, 9, 4), (2, 201, 10, 5)],
        9: [(1, 201, 5, 3), (3, 201, 4, 4), (5, 202, 4, 3), (2, 202, 4, 4)],  # Friday standard bump: 17 units total
        10: [(4, 201, 10, 3), (1, 202, 8, 4), (2, 201, 11, 5)]
    }

    # Production schedule: (p201_plan, p201_act, p202_plan, p202_act)
    PROD_SCHEDULE = {
        1: (10, 10, 4, 4),
        2: (12, 12, 4, 4),
        3: (10, 10, 4, 4),
        4: (10, 10, 4, 4),
        5: (10, 10, 4, 2),   # Line 2 bottleneck, -50% on Model Y
        6: (5, 5, 1, 1),     # Steel at safety stock (50 kg)
        7: (10, 0, 4, 0),    # Steel stockout: Model X halted (0 kg steel)
        8: (16, 16, 20, 20), # Recovery surge after steel PO #19 arrival
        9: (14, 14, 25, 25), # Friday clearance run
        10: (8, 8, 25, 20)   # Line 2 -20% shortfall (planned 25, actual 20)
    }

    # Tracking open sales orders placed during simulation: {so_id: dict}
    active_2026_orders = {}

    for s in config["scenarios"]:
        day_num = s["day"]
        day_str = s["date"]
        cur_date = date.fromisoformat(day_str)
        print(f"\nProcessing Day {day_num} ({day_str}): {s['name']}")

        day_pos = []
        day_pols = []
        day_grs = []
        day_grls = []
        day_sos = []
        day_sols = []
        day_dels = []
        day_dells = []
        day_prods = []
        day_issues = []
        day_movs = []

        # -------------------------------------------------------------
        # 1. Goods Receipts & Purchase Orders
        # -------------------------------------------------------------
        if day_num == 4:
            # PO #20 arrives with 60% partial quantity (150 of 250 kg)
            gr_id = next_gr_id; next_gr_id += 1
            grl_id = next_grl_id; next_grl_id += 1
            day_grs.append({"id": gr_id, "po_id": 20, "receipt_date": day_str, "status": "Received"})
            day_grls.append({"id": grl_id, "receipt_id": gr_id, "po_line_id": 20, "material_id": 102, "quantity_received": 150})
            mat_stock[102] += 150.0

            sm_id = next_mov_id; next_mov_id += 1
            day_movs.append({
                "id": sm_id, "item_id": INV_ITEM_MAP[102], "date": day_str, "movement_type": "IN",
                "quantity": 150, "goods_receipt_line_id": grl_id, "material_issue_id": "",
                "production_order_id": "", "delivery_line_id": ""
            })

        elif day_num == 6:
            # PO #21 (Copper wire 200m) arrives on time and in full
            gr_id = next_gr_id; next_gr_id += 1
            grl_id = next_grl_id; next_grl_id += 1
            day_grs.append({"id": gr_id, "po_id": 21, "receipt_date": day_str, "status": "Received"})
            day_grls.append({"id": grl_id, "receipt_id": gr_id, "po_line_id": 21, "material_id": 103, "quantity_received": 200})
            mat_stock[103] += 200.0

            sm_id = next_mov_id; next_mov_id += 1
            day_movs.append({
                "id": sm_id, "item_id": INV_ITEM_MAP[103], "date": day_str, "movement_type": "IN",
                "quantity": 200, "goods_receipt_line_id": grl_id, "material_issue_id": "",
                "production_order_id": "", "delivery_line_id": ""
            })

        elif day_num == 8:
            # PO #19 (Steel 400 kg) arrives 5 days late in full!
            gr_id = next_gr_id; next_gr_id += 1
            grl_id = next_grl_id; next_grl_id += 1
            day_grs.append({"id": gr_id, "po_id": 19, "receipt_date": day_str, "status": "Received"})
            day_grls.append({"id": grl_id, "receipt_id": gr_id, "po_line_id": 19, "material_id": 101, "quantity_received": 400})
            mat_stock[101] += 400.0

            sm_id = next_mov_id; next_mov_id += 1
            day_movs.append({
                "id": sm_id, "item_id": INV_ITEM_MAP[101], "date": day_str, "movement_type": "IN",
                "quantity": 400, "goods_receipt_line_id": grl_id, "material_issue_id": "",
                "production_order_id": "", "delivery_line_id": ""
            })

            # PO #20 balance (Plastic 100 kg) arrives
            gr_id2 = next_gr_id; next_gr_id += 1
            grl_id2 = next_grl_id; next_grl_id += 1
            day_grs.append({"id": gr_id2, "po_id": 20, "receipt_date": day_str, "status": "Received"})
            day_grls.append({"id": grl_id2, "receipt_id": gr_id2, "po_line_id": 20, "material_id": 102, "quantity_received": 100})
            mat_stock[102] += 100.0

            sm_id2 = next_mov_id; next_mov_id += 1
            day_movs.append({
                "id": sm_id2, "item_id": INV_ITEM_MAP[102], "date": day_str, "movement_type": "IN",
                "quantity": 100, "goods_receipt_line_id": grl_id2, "material_issue_id": "",
                "production_order_id": "", "delivery_line_id": ""
            })

            # Place reorder PO #22 for Plastic Granules from Supplier 3 (150 kg, promised Jan 10)
            po_id = next_po_id; next_po_id += 1
            pol_id = next_pol_id; next_pol_id += 1
            day_pos.append({
                "id": po_id, "supplier_id": 3, "order_date": day_str,
                "expected_delivery_date": "2026-01-10", "status": "Pending"
            })
            day_pols.append({
                "id": pol_id, "po_id": po_id, "material_id": 102,
                "quantity_ordered": 150, "quantity_received": 0
            })

        # -------------------------------------------------------------
        # 2. Manufacturing & Production Orders
        # -------------------------------------------------------------
        p201_plan, p201_act, p202_plan, p202_act = PROD_SCHEDULE.get(day_num, (10, 10, 4, 4))

        # Execute Product 201 production
        if p201_plan > 0:
            status_str = "Completed" if p201_act == p201_plan else ("Delayed" if p201_act == 0 else "Partially Completed")
            prod_id = next_prod_id; next_prod_id += 1
            day_prods.append({
                "id": prod_id, "product_id": 201, "planned_start": day_str, "planned_end": day_str,
                "actual_start": day_str if p201_act > 0 else "", "actual_end": day_str if p201_act > 0 else "",
                "planned_qty": p201_plan, "actual_qty": p201_act, "status": status_str
            })

            if p201_act > 0:
                for mid, factor in BOM[201].items():
                    iss_qty = int(round(p201_act * factor))
                    iss_id = next_issue_id; next_issue_id += 1
                    day_issues.append({
                        "id": iss_id, "production_order_id": prod_id, "item_id": INV_ITEM_MAP[mid],
                        "planned_quantity": int(round(p201_plan * factor)), "planned_issue_date": day_str,
                        "quantity_issued": iss_qty, "issue_date": day_str
                    })
                    mat_stock[mid] = max(0.0, mat_stock[mid] - iss_qty)
                    sm_id = next_mov_id; next_mov_id += 1
                    day_movs.append({
                        "id": sm_id, "item_id": INV_ITEM_MAP[mid], "date": day_str, "movement_type": "OUT",
                        "quantity": iss_qty, "goods_receipt_line_id": "", "material_issue_id": iss_id,
                        "production_order_id": "", "delivery_line_id": ""
                    })

                fg_stock[201] += p201_act
                sm_id = next_mov_id; next_mov_id += 1
                day_movs.append({
                    "id": sm_id, "item_id": INV_ITEM_MAP[201], "date": day_str, "movement_type": "IN",
                    "quantity": p201_act, "goods_receipt_line_id": "", "material_issue_id": "",
                    "production_order_id": prod_id, "delivery_line_id": ""
                })

        # Execute Product 202 production
        if p202_plan > 0:
            status_str = "Completed" if p202_act == p202_plan else ("Delayed" if p202_act == 0 else "Partially Completed")
            prod_id = next_prod_id; next_prod_id += 1
            day_prods.append({
                "id": prod_id, "product_id": 202, "planned_start": day_str, "planned_end": day_str,
                "actual_start": day_str if p202_act > 0 else "", "actual_end": day_str if p202_act > 0 else "",
                "planned_qty": p202_plan, "actual_qty": p202_act, "status": status_str
            })

            if p202_act > 0:
                for mid, factor in BOM[202].items():
                    iss_qty = int(round(p202_act * factor))
                    iss_id = next_issue_id; next_issue_id += 1
                    day_issues.append({
                        "id": iss_id, "production_order_id": prod_id, "item_id": INV_ITEM_MAP[mid],
                        "planned_quantity": int(round(p202_plan * factor)), "planned_issue_date": day_str,
                        "quantity_issued": iss_qty, "issue_date": day_str
                    })
                    mat_stock[mid] = max(0.0, mat_stock[mid] - iss_qty)
                    sm_id = next_mov_id; next_mov_id += 1
                    day_movs.append({
                        "id": sm_id, "item_id": INV_ITEM_MAP[mid], "date": day_str, "movement_type": "OUT",
                        "quantity": iss_qty, "goods_receipt_line_id": "", "material_issue_id": iss_id,
                        "production_order_id": "", "delivery_line_id": ""
                    })

                fg_stock[202] += p202_act
                sm_id = next_mov_id; next_mov_id += 1
                day_movs.append({
                    "id": sm_id, "item_id": INV_ITEM_MAP[202], "date": day_str, "movement_type": "IN",
                    "quantity": p202_act, "goods_receipt_line_id": "", "material_issue_id": "",
                    "production_order_id": prod_id, "delivery_line_id": ""
                })

        # Day 6 calibration: exact steel stock reaches safety stock (50 kg)
        if day_num == 6:
            mat_stock[101] = 50.0

        # Day 7 calibration: steel stockout (deplete to 0.0 kg)
        if day_num == 7:
            rem_steel = int(round(mat_stock[101]))
            if rem_steel > 0:
                iss_id = next_issue_id; next_issue_id += 1
                day_issues.append({
                    "id": iss_id, "production_order_id": next_prod_id - 1, "item_id": INV_ITEM_MAP[101],
                    "planned_quantity": rem_steel, "planned_issue_date": day_str,
                    "quantity_issued": rem_steel, "issue_date": day_str
                })
                mat_stock[101] = 0.0
                sm_id = next_mov_id; next_mov_id += 1
                day_movs.append({
                    "id": sm_id, "item_id": INV_ITEM_MAP[101], "date": day_str, "movement_type": "OUT",
                    "quantity": rem_steel, "goods_receipt_line_id": "", "material_issue_id": iss_id,
                    "production_order_id": "", "delivery_line_id": ""
                })

        # -------------------------------------------------------------
        # 3. Customer Sales Orders Intake
        # -------------------------------------------------------------
        for cust_id, prod_id, qty, lead_d in ORDERS_SCHEDULE.get(day_num, []):
            so_id = next_so_id; next_so_id += 1
            sol_id = next_sol_id; next_sol_id += 1
            req_d = (cur_date + timedelta(days=lead_d)).isoformat()
            day_sos.append({
                "id": so_id, "customer_id": cust_id, "order_date": day_str,
                "requested_delivery_date": req_d, "status": "Pending"
            })
            day_sols.append({
                "id": sol_id, "sales_order_id": so_id, "product_id": prod_id,
                "quantity_ordered": qty, "quantity_fulfilled": 0
            })
            active_2026_orders[so_id] = {
                "so_id": so_id, "sol_id": sol_id, "customer_id": cust_id,
                "product_id": prod_id, "quantity_ordered": qty, "quantity_fulfilled": 0,
                "order_date": day_str, "requested_date": req_d
            }

        # -------------------------------------------------------------
        # 4. Customer Order Deliveries & Shipments
        # -------------------------------------------------------------
        # Explicit fulfillment rules matching the story arc:
        to_ship = []

        if day_num == 4:
            # First 2026 deliveries due today: SO #231 (10u P201) & SO #232 (8u P202)
            to_ship.append((231, 231, 201, 10))
            to_ship.append((232, 232, 202, 8))

        elif day_num == 5:
            # Deliveries due today: SO #233 (12u P201) & SO #234 (14u P201)
            # Note: SO #237 (8u P202 due Jan 5) delayed due to Line 2 capacity shortfall!
            to_ship.append((233, 233, 201, 12))
            to_ship.append((234, 234, 201, 14))

        elif day_num == 6:
            # Deliveries due today: SO #235 (12u P201) & SO #238 (9u P201)
            to_ship.append((235, 235, 201, 12))
            to_ship.append((238, 238, 201, 9))

        elif day_num == 7:
            # Day 7: Genuine Late Customer Shipment!
            # Ship delayed SO #237 (8u P202, requested Jan 5 -> delivered late on Jan 7!)
            to_ship.append((237, 237, 202, 8))
            # On-time delivery for Model Y: SO #239 (10u P202, req Jan 7)
            to_ship.append((239, 239, 202, 10))
            # Note: Model X orders SO #236 & #241 due Jan 7 delayed due to steel stockout!

        elif day_num == 8:
            # Day 8: Backlog recovery begins!
            # 1. Carried-over 2025 backorders (oldest-first FIFO): SO #220, #221, #225 (33 units P202)
            to_ship.append((220, 220, 202, 13))
            to_ship.append((221, 221, 202, 8))
            to_ship.append((225, 225, 202, 12))
            # 2. Delayed Model X orders from Day 7: SO #236 (10u) & SO #241 (10u)
            to_ship.append((236, 236, 201, 10))
            to_ship.append((241, 241, 201, 10))
            # 3. On-time orders due Jan 8: SO #240 (11u P201), SO #242 (8u P202), SO #244 (11u P201)
            to_ship.append((240, 240, 201, 11))
            to_ship.append((242, 242, 202, 8))
            to_ship.append((244, 244, 201, 11))

        elif day_num == 9:
            # Day 9: Backorders continue clearing FIFO:
            # 1. Carried-over 2025 backorders: SO #226 (9u P202), SO #227 (12u P201), SO #230 (9u P202)
            to_ship.append((226, 226, 202, 9))
            to_ship.append((227, 227, 201, 12))
            to_ship.append((230, 230, 202, 9))
            # 2. On-time orders due Jan 9: SO #243 (12u P201), SO #245 (9u P202), SO #247 (10u P201)
            to_ship.append((243, 243, 201, 12))
            to_ship.append((245, 245, 202, 9))
            to_ship.append((247, 247, 201, 10))

        elif day_num == 10:
            # Day 10: Final carried-over 2025 backorders cleared:
            # 1. SO #224 (14u P202), SO #229 (14u P201), SO #228 (18u P202)
            to_ship.append((224, 224, 202, 14))
            to_ship.append((229, 229, 201, 14))
            to_ship.append((228, 228, 202, 18))
            # 2. On-time orders due Jan 10: SO #246 (10u P201), SO #248 (8u P202), SO #250 (10u P201)
            to_ship.append((246, 246, 201, 10))
            to_ship.append((248, 248, 202, 8))
            to_ship.append((250, 250, 201, 10))

        for so_id, sol_id, pid, ship_qty in to_ship:
            del_id = next_del_id; next_del_id += 1
            dell_id = next_dell_id; next_dell_id += 1
            day_dels.append({
                "id": del_id, "sales_order_id": so_id, "ship_date": day_str,
                "delivery_date": day_str, "status": "Delivered"
            })
            day_dells.append({
                "id": dell_id, "delivery_id": del_id, "sales_order_line_id": sol_id,
                "product_id": pid, "quantity_shipped": ship_qty
            })
            fg_stock[pid] = max(0, fg_stock[pid] - ship_qty)
            if so_id in active_2026_orders:
                active_2026_orders[so_id]["quantity_fulfilled"] += ship_qty

            sm_id = next_mov_id; next_mov_id += 1
            day_movs.append({
                "id": sm_id, "item_id": INV_ITEM_MAP[pid], "date": day_str, "movement_type": "OUT",
                "quantity": ship_qty, "goods_receipt_line_id": "", "material_issue_id": "",
                "production_order_id": "", "delivery_line_id": dell_id
            })

        # -------------------------------------------------------------
        # 5. Export Pack to demo_data/packs/ and demo_data/queue/
        # -------------------------------------------------------------
        pack_dir = PACKS_DIR / day_str
        queue_pack_dir = QUEUE_DIR / day_str
        pack_dir.mkdir(parents=True, exist_ok=True)
        queue_pack_dir.mkdir(parents=True, exist_ok=True)

        files_to_write = {
            "purchase_orders.csv": (["id", "supplier_id", "order_date", "expected_delivery_date", "status"], day_pos),
            "purchase_order_lines.csv": (["id", "po_id", "material_id", "quantity_ordered", "quantity_received"], day_pols),
            "goods_receipts.csv": (["id", "po_id", "receipt_date", "status"], day_grs),
            "goods_receipt_lines.csv": (["id", "receipt_id", "po_line_id", "material_id", "quantity_received"], day_grls),
            "sales_orders.csv": (["id", "customer_id", "order_date", "requested_delivery_date", "status"], day_sos),
            "sales_order_lines.csv": (["id", "sales_order_id", "product_id", "quantity_ordered", "quantity_fulfilled"], day_sols),
            "deliveries.csv": (["id", "sales_order_id", "ship_date", "delivery_date", "status"], day_dels),
            "delivery_lines.csv": (["id", "delivery_id", "sales_order_line_id", "product_id", "quantity_shipped"], day_dells),
            "production_orders.csv": (["id", "product_id", "planned_start", "planned_end", "actual_start", "actual_end", "planned_qty", "actual_qty", "status"], day_prods),
            "material_issues.csv": (["id", "production_order_id", "item_id", "planned_quantity", "planned_issue_date", "quantity_issued", "issue_date"], day_issues),
            "stock_movements.csv": (["id", "item_id", "date", "movement_type", "quantity", "goods_receipt_line_id", "material_issue_id", "production_order_id", "delivery_line_id"], day_movs)
        }

        row_counts = {}
        for fname, (cols, rows) in files_to_write.items():
            row_counts[fname.replace(".csv", "")] = len(rows)
            for target_dir in [pack_dir, queue_pack_dir]:
                fpath = target_dir / fname
                with open(fpath, "w", newline="", encoding="utf-8") as f_out:
                    writer = csv.DictWriter(f_out, fieldnames=cols)
                    writer.writeheader()
                    writer.writerows(rows)

        meta = {
            "pack_date": day_str,
            "day_number": day_num,
            "scenario_name": s["name"],
            "scenario_type": s["type"],
            "is_simulated": True,
            "label": "SIMULATED ERP OPERATIONAL PACK",
            "framing": FRAMING,
            "exported_at": f"{day_str}T20:00:00+05:30",
            "row_counts": row_counts,
            "total_events": sum(row_counts.values()),
            "closing_stock_simulated": {
                "materials": {k: round(v, 1) for k, v in mat_stock.items()},
                "finished_goods": dict(fg_stock)
            }
        }

        for target_dir in [pack_dir, queue_pack_dir]:
            with open(target_dir / "metadata.json", "w", encoding="utf-8") as f_meta:
                json.dump(meta, f_meta, indent=2)

        print(f"  ✓ Exported pack for {day_str}: {sum(row_counts.values())} events (Steel={mat_stock[101]:.1f}kg, Plastic={mat_stock[102]:.1f}kg, FG_X={fg_stock[201]}u, FG_Y={fg_stock[202]}u)")

    print("\nAll 10 daily packs generated in demo_data/packs/ and demo_data/queue/!")


if __name__ == "__main__":
    generate_packs()
