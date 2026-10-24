"""
stage10/demo_feed/generate_demo_feed.py — Deterministic Scripted Feed Generator for 2026 Demo Days (Jan 1 - Jan 10)

Implements SAGE Stage 9 FINAL 3 (Part 2.3):
- Generates 10 daily packs for 2026-01-01 through 2026-01-10 into demo_data/packs/ and demo_data/queue/
- Strictly respects master data, BOM relationships, lead times, and deterministic parameters.
- Re-calculates closing stock and statuses as of each pack day.
- Follows the pre-registered scenario script (scenario_script.yaml):
    1. Jan 1: Normal operations
    2. Jan 2: Widget Model X demand spike (buffer absorbs)
    3. Jan 3: Supplier 4 steel delivery overdue (buffer holds)
    4. Jan 4: Plastic 60% partial receipt, steel 1d late
    5. Jan 5: Line 2 capacity disruption, Widget Model Y -50%
    6. Jan 6: Steel 3d overdue, steel at safety, first customer orders overdue, copper arrives on time
    7. Jan 7: Steel stockout (0 kg), Widget Model X halted, customer backlog escalates
    8. Jan 8: Steel arrives 5d late (in full), plastic balance arrives, production resumes, backlog burns down
    9. Jan 9: Seasonal Friday demand peak (control), backlog continues clearing
   10. Jan 10: Dual minor issues: Widget Y -20% and late plastic reorder PO #22. Backlog nearly cleared.
"""

from __future__ import annotations

import csv
from datetime import date, timedelta, datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sys
import yaml

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
PACKS_DIR = ROOT_DIR / "demo_data" / "packs"
QUEUE_DIR = ROOT_DIR / "demo_data" / "queue"
CONFIG_PATH = ROOT_DIR / "stage10" / "demo_feed" / "scenario_script.yaml"

FRAMING = "SAGE performs controlled synthetic causal-attribution evaluation under an expert-defined causal model; it does not claim to prove real-world causality."


def generate_packs():
    print("=" * 70)
    print("SAGE Stage 9 FINAL 3: Generating Ten-Day Demo Feed (1–10 Jan 2026)")
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

    # Opening position on 2025-12-31:
    # Materials: 101: 215 kg, 102: 140 kg, 103: 110 m
    # Finished Goods: 201: 25 units, 202: 20 units
    mat_stock = {101: 215.0, 102: 140.0, 103: 110.0}
    fg_stock = {201: 25, 202: 20}

    # Tracking persistent simulation state across days
    open_sales_orders = []    # list of active sales orders
    open_pos = {
        19: {"supplier_id": 4, "material_id": 101, "ordered_qty": 400, "rec_qty": 0, "order_date": "2025-12-25", "expected_date": "2026-01-02", "status": "Pending"},
        20: {"supplier_id": 3, "material_id": 102, "ordered_qty": 250, "rec_qty": 0, "order_date": "2025-12-21", "expected_date": "2026-01-04", "status": "Pending"},
        21: {"supplier_id": 5, "material_id": 103, "ordered_qty": 200, "rec_qty": 0, "order_date": "2025-12-25", "expected_date": "2026-01-06", "status": "Pending"}
    }

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

    # Day definitions
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
        # 1. Goods Receipts (Inbound Shipments)
        # -------------------------------------------------------------
        if day_num == 4:
            # PO #20 arrives with 60% partial quantity (150 of 250 kg)
            gr_id = next_gr_id; next_gr_id += 1
            grl_id = next_grl_id; next_grl_id += 1
            day_grs.append({"id": gr_id, "po_id": 20, "receipt_date": day_str, "status": "Received"})
            day_grls.append({"id": grl_id, "receipt_id": gr_id, "po_line_id": 20, "material_id": 102, "quantity_received": 150})
            open_pos[20]["rec_qty"] = 150
            open_pos[20]["status"] = "Partial"
            mat_stock[102] += 150.0

            # Stock movement for receipt
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
            open_pos[21]["rec_qty"] = 200
            open_pos[21]["status"] = "Complete"
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
            open_pos[19]["rec_qty"] = 400
            open_pos[19]["status"] = "Complete"
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
            open_pos[20]["rec_qty"] = 250
            open_pos[20]["status"] = "Complete"
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
            open_pos[po_id] = {
                "supplier_id": 3, "material_id": 102, "ordered_qty": 150,
                "rec_qty": 0, "order_date": day_str, "expected_date": "2026-01-10", "status": "Pending"
            }

        # -------------------------------------------------------------
        # 2. Manufacturing & Production Orders
        # -------------------------------------------------------------
        # Planned production targets
        p201_plan = 10
        p202_plan = 4

        if day_num == 1:
            p201_act = 10
            p202_act = 4
        elif day_num == 2:
            p201_act = 12
            p202_act = 4
        elif day_num == 3:
            p201_act = 10
            p202_act = 4
        elif day_num == 4:
            p201_act = 10
            p202_act = 4
        elif day_num == 5:
            # Capacity disruption: Line 2 downtime, Widget Y -50% (planned 4, actual 2)
            p201_act = 10
            p202_act = 2
        elif day_num == 6:
            # Steel reaches safety level, production short (cut to 6 units)
            p201_plan = 12
            p201_act = 6
            p202_act = 1
        elif day_num == 7:
            # Steel stockout: Widget X halted completely (0 units)
            p201_plan = 10
            p201_act = 0
            p202_plan = 4
            p202_act = 0
        elif day_num == 8:
            # Recovery surge: production resumes in full
            p201_plan = 16
            p201_act = 16
            p202_plan = 6
            p202_act = 6
        elif day_num == 9:
            # High throughput for clearance
            p201_plan = 14
            p201_act = 14
            p202_plan = 4
            p202_act = 4
        elif day_num == 10:
            # Dual issues: Widget Y -20% below plan (planned 5, actual 4)
            p201_plan = 8
            p201_act = 8
            p202_plan = 5
            p202_act = 4
        else:
            p201_act = p201_plan
            p202_act = p202_plan

        # Execute Product 201 production if planned > 0
        if p201_plan > 0:
            status_str = "Completed" if p201_act == p201_plan else ("Delayed" if p201_act == 0 else "Partially Completed")
            prod_id = next_prod_id; next_prod_id += 1
            day_prods.append({
                "id": prod_id, "product_id": 201, "planned_start": day_str, "planned_end": day_str,
                "actual_start": day_str if p201_act > 0 else "", "actual_end": day_str if p201_act > 0 else "",
                "planned_qty": p201_plan, "actual_qty": p201_act, "status": status_str
            })

            # Material issues and stock adjustments for 201
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

                # FG IN movement
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

                # FG IN movement
                fg_stock[202] += p202_act
                sm_id = next_mov_id; next_mov_id += 1
                day_movs.append({
                    "id": sm_id, "item_id": INV_ITEM_MAP[202], "date": day_str, "movement_type": "IN",
                    "quantity": p202_act, "goods_receipt_line_id": "", "material_issue_id": "",
                    "production_order_id": prod_id, "delivery_line_id": ""
                })

        # Day 7: Deplete remaining steel buffer to 0.0 kg (Stockout event)
        if day_num == 7:
            rem_steel = int(mat_stock[101])
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
        # 3. Customer Sales Orders
        # -------------------------------------------------------------
        new_orders = []
        if day_num == 1:
            new_orders = [(1, 201, 5, 1), (2, 202, 3, 1)]
        elif day_num == 2:
            # Demand spike on 201 (~28 units, 2.8x normal)
            new_orders = [(1, 201, 16, 1), (3, 201, 12, 1), (2, 202, 4, 1)]
        elif day_num == 3:
            new_orders = [(4, 201, 10, 1), (5, 202, 4, 1)]
        elif day_num == 4:
            new_orders = [(1, 201, 10, 1), (2, 202, 4, 1)]
        elif day_num == 5:
            new_orders = [(3, 201, 10, 1), (4, 202, 4, 1)]
        elif day_num == 6:
            # Elevated demand on 201 (14 units)
            new_orders = [(1, 201, 8, 1), (2, 201, 6, 1), (5, 202, 4, 1)]
        elif day_num == 7:
            new_orders = [(2, 201, 10, 1), (3, 202, 4, 1)]
        elif day_num == 8:
            new_orders = [(4, 201, 8, 1), (1, 202, 4, 1)]
        elif day_num == 9:
            # Friday seasonal peak (control, 1.25x normal)
            new_orders = [(1, 201, 6, 1), (2, 202, 4, 1)]
        elif day_num == 10:
            new_orders = [(3, 201, 6, 1), (4, 202, 4, 1)]

        for cust_id, prod_id, qty, lead_d in new_orders:
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
            open_sales_orders.append({
                "so_id": so_id, "sol_id": sol_id, "customer_id": cust_id,
                "product_id": prod_id, "quantity_ordered": qty, "quantity_fulfilled": 0,
                "order_date": day_str, "requested_date": req_d
            })

        # -------------------------------------------------------------
        # 4. Order Fulfillment & Deliveries
        # -------------------------------------------------------------
        # Fulfill orders requested on or before today if FG stock allows
        deliverable_orders = [o for o in open_sales_orders if o["requested_date"] <= day_str and o["quantity_fulfilled"] < o["quantity_ordered"]]
        deliverable_orders.sort(key=lambda x: x["requested_date"])

        for o in deliverable_orders:
            pid = o["product_id"]
            rem = o["quantity_ordered"] - o["quantity_fulfilled"]
            ship_qty = min(rem, fg_stock[pid])

            # In Day 6 & 7, stockouts restrict shipments of Widget Model X
            if ship_qty > 0:
                del_id = next_del_id; next_del_id += 1
                dell_id = next_dell_id; next_dell_id += 1
                day_dels.append({
                    "id": del_id, "sales_order_id": o["so_id"], "ship_date": day_str,
                    "delivery_date": day_str, "status": "Delivered"
                })
                day_dells.append({
                    "id": dell_id, "delivery_id": del_id, "sales_order_line_id": o["sol_id"],
                    "product_id": pid, "quantity_shipped": ship_qty
                })
                fg_stock[pid] -= ship_qty
                o["quantity_fulfilled"] += ship_qty

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

        print(f"  ✓ Exported pack for {day_str}: {sum(row_counts.values())} events (Steel Stock={mat_stock[101]:.1f}kg, Widget X Stock={fg_stock[201]}u)")

    print("\nAll 10 daily packs generated in demo_data/packs/ and demo_data/queue/!")


if __name__ == "__main__":
    generate_packs()
