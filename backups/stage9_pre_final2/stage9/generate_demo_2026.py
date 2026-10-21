"""
stage9/generate_demo_2026.py — Simulation Extension and Pack Generator for 2026 Demo Days.

Generates 2026-01-01 to 2026-01-10 data in sage_ext and exports 10 daily packs into demo_data/packs/
and demo_data/queue/.

Adheres strictly to Stage 9 FINAL specification:
- B1: Continues from year-end 2025-12-31 state in sage_ext.
- B2: Uses incidents_demo_2026.yaml:
      * 1-2 Jan: Normal
      * 3-8 Jan: Supplier 1 delay on Material 101 (expected Jan 3, arrives Jan 8)
      * 6-8 Jan: Demand spike on Product 201
      * 9-10 Jan: Normal recovery
      Logs answer key to business_events_demo in sage_ext.
- B3: Prepares for live/sage_live.db initialization.
- B4: Exports demo_data/packs/2026-01-01 to 2026-01-10 (CSV + metadata.json).
"""

from __future__ import annotations

import csv
from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
import random
import shutil
import sys
import yaml

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import create_engine, text
from app.database import SessionLocal, Base
from app.models.inventory import InventoryItem, Product, StockMovement, BillOfMaterials
from app.models.suppliers import Supplier
from app.models.purchasing import PurchaseOrder, PurchaseOrderLine, GoodsReceipt, GoodsReceiptLine
from app.models.production import ProductionOrder, MaterialIssue
from app.models.sales import Customer, SalesOrder, SalesOrderLine, Delivery, DeliveryLine

PACKS_DIR = ROOT_DIR / "demo_data" / "packs"
QUEUE_DIR = ROOT_DIR / "demo_data" / "queue"
INCIDENTS_CONFIG_PATH = ROOT_DIR / "stage9" / "config" / "incidents_demo_2026.yaml"

FRAMING = "SAGE performs controlled synthetic causal-attribution evaluation under an expert-defined causal model; it does not claim to prove real-world causality."

EXPECTED_COLUMNS = {
    "purchase_orders": ["id", "supplier_id", "order_date", "expected_delivery_date", "status"],
    "purchase_order_lines": ["id", "po_id", "material_id", "quantity_ordered", "quantity_received"],
    "goods_receipts": ["id", "po_id", "receipt_date", "status"],
    "goods_receipt_lines": ["id", "receipt_id", "po_line_id", "material_id", "quantity_received"],
    "sales_orders": ["id", "customer_id", "order_date", "requested_delivery_date", "status"],
    "sales_order_lines": ["id", "sales_order_id", "product_id", "quantity_ordered", "quantity_fulfilled"],
    "deliveries": ["id", "sales_order_id", "ship_date", "delivery_date", "status"],
    "delivery_lines": ["id", "delivery_id", "sales_order_line_id", "product_id", "quantity_shipped"],
    "production_orders": ["id", "product_id", "planned_start", "planned_end", "actual_start", "actual_end", "planned_qty", "actual_qty", "status"],
    "material_issues": ["id", "production_order_id", "item_id", "planned_quantity", "planned_issue_date", "quantity_issued", "issue_date"],
    "stock_movements": ["id", "item_id", "date", "movement_type", "quantity", "goods_receipt_line_id", "material_issue_id", "production_order_id", "delivery_line_id"]
}


def run_demo_simulation():
    print("=" * 70)
    print("RUNNING SAGE DEMO EXTENSION (2026-01-01 to 2026-01-10) ON sage_ext")
    print("=" * 70)

    db = SessionLocal(source="ext")

    # Clean existing 2026 data in sage_ext if any
    print("Cleaning any existing 2026 data in sage_ext...")
    db.execute(text("DELETE FROM stock_movements WHERE date >= '2026-01-01'"))
    db.execute(text("DELETE FROM delivery_lines WHERE delivery_id IN (SELECT id FROM deliveries WHERE ship_date >= '2026-01-01')"))
    db.execute(text("DELETE FROM deliveries WHERE ship_date >= '2026-01-01'"))
    db.execute(text("DELETE FROM sales_order_lines WHERE sales_order_id IN (SELECT id FROM sales_orders WHERE order_date >= '2026-01-01')"))
    db.execute(text("DELETE FROM sales_orders WHERE order_date >= '2026-01-01'"))
    db.execute(text("DELETE FROM material_issues WHERE planned_issue_date >= '2026-01-01'"))
    db.execute(text("DELETE FROM production_orders WHERE planned_start >= '2026-01-01'"))
    db.execute(text("DELETE FROM goods_receipt_lines WHERE receipt_id IN (SELECT id FROM goods_receipts WHERE receipt_date >= '2026-01-01')"))
    db.execute(text("DELETE FROM goods_receipts WHERE receipt_date >= '2026-01-01'"))
    db.execute(text("DELETE FROM purchase_order_lines WHERE po_id IN (SELECT id FROM purchase_orders WHERE order_date >= '2026-01-01')"))
    db.execute(text("DELETE FROM purchase_orders WHERE order_date >= '2026-01-01'"))
    db.execute(text("DELETE FROM business_events_demo"))
    db.commit()

    # Load master data
    inventory_items = {item.id: item for item in db.query(InventoryItem).all()}
    item_by_product = {item.product_id: item for item in inventory_items.values()}
    products = {p.id: p for p in db.query(Product).all()}
    suppliers = {s.id: s for s in db.query(Supplier).all()}
    customers = {c.id: c for c in db.query(Customer).all()}
    boms = db.query(BillOfMaterials).all()

    # Compute inventory stock at 2025-12-31
    current_stock = {}
    for item_id, item in inventory_items.items():
        in_qty = db.execute(text(
            "SELECT COALESCE(SUM(quantity), 0) FROM stock_movements WHERE item_id = :item_id AND movement_type = 'IN' AND date <= '2025-12-31'"
        ), {"item_id": item_id}).scalar() or 0
        out_qty = db.execute(text(
            "SELECT COALESCE(SUM(quantity), 0) FROM stock_movements WHERE item_id = :item_id AND movement_type = 'OUT' AND date <= '2025-12-31'"
        ), {"item_id": item_id}).scalar() or 0
        current_stock[item.product_id] = float(item.opening_balance_qty + in_qty - out_qty)

    print("Initial 2026 stock levels (at 2025-12-31):", current_stock)

    # Next IDs
    next_ids = {
        "po": (db.execute(text("SELECT COALESCE(MAX(id), 0) FROM purchase_orders")).scalar() or 0) + 1,
        "pol": (db.execute(text("SELECT COALESCE(MAX(id), 0) FROM purchase_order_lines")).scalar() or 0) + 1,
        "gr": (db.execute(text("SELECT COALESCE(MAX(id), 0) FROM goods_receipts")).scalar() or 0) + 1,
        "grl": (db.execute(text("SELECT COALESCE(MAX(id), 0) FROM goods_receipt_lines")).scalar() or 0) + 1,
        "prod": (db.execute(text("SELECT COALESCE(MAX(id), 0) FROM production_orders")).scalar() or 0) + 1,
        "issue": (db.execute(text("SELECT COALESCE(MAX(id), 0) FROM material_issues")).scalar() or 0) + 1,
        "mov": (db.execute(text("SELECT COALESCE(MAX(id), 0) FROM stock_movements")).scalar() or 0) + 1,
        "so": (db.execute(text("SELECT COALESCE(MAX(id), 0) FROM sales_orders")).scalar() or 0) + 1,
        "sol": (db.execute(text("SELECT COALESCE(MAX(id), 0) FROM sales_order_lines")).scalar() or 0) + 1,
        "deliv": (db.execute(text("SELECT COALESCE(MAX(id), 0) FROM deliveries")).scalar() or 0) + 1,
        "dell": (db.execute(text("SELECT COALESCE(MAX(id), 0) FROM delivery_lines")).scalar() or 0) + 1,
    }

    # Log ground truth to business_events_demo
    db.execute(text("""
        INSERT INTO business_events_demo (id, incident_id, incident_type, category, entity_type, entity_id, start_date, end_date, parameters, created_at)
        VALUES
        (1, 'DEMO_2026_INC_01', 'supplier_delay', 'supply', 'supplier', 1, '2026-01-03', '2026-01-08',
         '{"target_material": 101, "promised_delivery": "2026-01-03", "actual_receipt": "2026-01-08", "delay_days": 5}', NOW()),
        (2, 'DEMO_2026_INC_02', 'demand_spike', 'demand', 'product', 201, '2026-01-06', '2026-01-08',
         '{"target_product": 201, "demand_multiplier": 1.85, "duration_days": 3}', NOW())
    """))
    db.commit()
    print("Logged ground truth answer key to business_events_demo.")

    # Storage for day pack generation
    day_records = {date(2026, 1, d): {tbl: [] for tbl in EXPECTED_COLUMNS} for d in range(1, 11)}

    # Track open orders across 10 days
    demo_po_101 = None
    demo_po_101_line = None

    for d_num in range(1, 11):
        cur_date = date(2026, 1, d_num)
        print(f"\n--- Simulating {cur_date} (Day {d_num}/10) ---")

        # 1. Day 1 (Jan 1): Place Purchase Order for Material 101 with Supplier 1
        if d_num == 1:
            po_id = next_ids["po"]
            pol_id = next_ids["pol"]
            next_ids["po"] += 1
            next_ids["pol"] += 1

            po_dict = {
                "id": po_id,
                "supplier_id": 1,
                "order_date": cur_date.strftime("%Y-%m-%d"),
                "expected_delivery_date": "2026-01-03",
                "status": "Pending"
            }
            pol_dict = {
                "id": pol_id,
                "po_id": po_id,
                "material_id": 101,
                "quantity_ordered": 350,
                "quantity_received": 0
            }
            day_records[cur_date]["purchase_orders"].append(po_dict)
            day_records[cur_date]["purchase_order_lines"].append(pol_dict)
            demo_po_101 = po_dict
            demo_po_101_line = pol_dict
            print(f"Placed PO {po_id} with Supplier 1 for 350 units Material 101 (promised 2026-01-03).")

        # 2. Day 8 (Jan 8): Delayed delivery arrives!
        if d_num == 8 and demo_po_101 is not None:
            gr_id = next_ids["gr"]
            grl_id = next_ids["grl"]
            mov_id = next_ids["mov"]
            next_ids["gr"] += 1
            next_ids["grl"] += 1
            next_ids["mov"] += 1

            gr_dict = {
                "id": gr_id,
                "po_id": demo_po_101["id"],
                "receipt_date": cur_date.strftime("%Y-%m-%d"),
                "status": "Received"
            }
            grl_dict = {
                "id": grl_id,
                "receipt_id": gr_id,
                "po_line_id": demo_po_101_line["id"],
                "material_id": 101,
                "quantity_received": 350
            }
            mov_dict = {
                "id": mov_id,
                "item_id": item_by_product[101].id,
                "date": cur_date.strftime("%Y-%m-%d"),
                "movement_type": "IN",
                "quantity": 350,
                "goods_receipt_line_id": grl_id,
                "material_issue_id": None,
                "production_order_id": None,
                "delivery_line_id": None
            }
            day_records[cur_date]["goods_receipts"].append(gr_dict)
            day_records[cur_date]["goods_receipt_lines"].append(grl_dict)
            day_records[cur_date]["stock_movements"].append(mov_dict)
            current_stock[101] += 350
            print(f"Goods Receipt {gr_id} arrived for PO {demo_po_101['id']}: 350 units Material 101! New stock: {current_stock[101]}")

        # 3. Customer Demand & Sales Orders
        # Jan 6-8: Demand spike on Product 201 (multiplier ~1.85)
        is_spike = (6 <= d_num <= 8)
        p201_qty = int(14 * 1.85) if is_spike else 14
        p202_qty = 10

        # Customer 1 orders Product 201
        so_id1 = next_ids["so"]
        sol_id1 = next_ids["sol"]
        next_ids["so"] += 1
        next_ids["sol"] += 1

        so_dict1 = {
            "id": so_id1,
            "customer_id": 1,
            "order_date": cur_date.strftime("%Y-%m-%d"),
            "requested_delivery_date": (cur_date + timedelta(days=2)).strftime("%Y-%m-%d"),
            "status": "Pending"
        }
        sol_dict1 = {
            "id": sol_id1,
            "sales_order_id": so_id1,
            "product_id": 201,
            "quantity_ordered": p201_qty,
            "quantity_fulfilled": 0
        }
        day_records[cur_date]["sales_orders"].append(so_dict1)
        day_records[cur_date]["sales_order_lines"].append(sol_dict1)

        # Customer 2 orders Product 202
        so_id2 = next_ids["so"]
        sol_id2 = next_ids["sol"]
        next_ids["so"] += 1
        next_ids["sol"] += 1

        so_dict2 = {
            "id": so_id2,
            "customer_id": 2,
            "order_date": cur_date.strftime("%Y-%m-%d"),
            "requested_delivery_date": (cur_date + timedelta(days=2)).strftime("%Y-%m-%d"),
            "status": "Pending"
        }
        sol_dict2 = {
            "id": sol_id2,
            "sales_order_id": so_id2,
            "product_id": 202,
            "quantity_ordered": p202_qty,
            "quantity_fulfilled": 0
        }
        day_records[cur_date]["sales_orders"].append(so_dict2)
        day_records[cur_date]["sales_order_lines"].append(sol_dict2)
        print(f"Customer orders: Product 201 = {p201_qty} units (Spike={is_spike}), Product 202 = {p202_qty} units.")

        # 4. Production
        # Weekdays: build if raw materials are available.
        # Notice: Product 201 needs 1.0 units of Material 101, 1.0 of 102, 1.0 of 103 per unit.
        # From Jan 1-7, Material 101 is only 9 units! Batch size is 30. So max producible = 0!
        # Production will be Delayed with shortfall = 30.
        # On Jan 8+, Material 101 is 359 units, so production succeeds!
        if cur_date.weekday() < 5:  # Weekday
            for p_id, batch_size in [(201, 30), (202, 20)]:
                prod_id = next_ids["prod"]
                next_ids["prod"] += 1

                mat101_avail = current_stock[101]
                mat102_avail = current_stock[102]
                mat103_avail = current_stock[103]

                # Can produce only if enough materials
                can_produce = (mat101_avail >= batch_size and mat102_avail >= batch_size and mat103_avail >= batch_size)
                actual_qty = batch_size if can_produce else 0
                prod_status = "Completed" if actual_qty == batch_size else "Delayed"

                prod_dict = {
                    "id": prod_id,
                    "product_id": p_id,
                    "planned_start": cur_date.strftime("%Y-%m-%d"),
                    "planned_end": cur_date.strftime("%Y-%m-%d"),
                    "actual_start": cur_date.strftime("%Y-%m-%d") if actual_qty > 0 else None,
                    "actual_end": cur_date.strftime("%Y-%m-%d") if actual_qty > 0 else None,
                    "planned_qty": batch_size,
                    "actual_qty": actual_qty,
                    "status": prod_status
                }
                day_records[cur_date]["production_orders"].append(prod_dict)

                if actual_qty > 0:
                    # Issue materials
                    for m_id in [101, 102, 103]:
                        iss_id = next_ids["issue"]
                        mov_out_id = next_ids["mov"]
                        next_ids["issue"] += 1
                        next_ids["mov"] += 1

                        iss_dict = {
                            "id": iss_id,
                            "production_order_id": prod_id,
                            "item_id": item_by_product[m_id].id,
                            "planned_quantity": actual_qty,
                            "planned_issue_date": cur_date.strftime("%Y-%m-%d"),
                            "quantity_issued": actual_qty,
                            "issue_date": cur_date.strftime("%Y-%m-%d")
                        }
                        mov_out_dict = {
                            "id": mov_out_id,
                            "item_id": item_by_product[m_id].id,
                            "date": cur_date.strftime("%Y-%m-%d"),
                            "movement_type": "OUT",
                            "quantity": actual_qty,
                            "goods_receipt_line_id": None,
                            "material_issue_id": iss_id,
                            "production_order_id": None,
                            "delivery_line_id": None
                        }
                        day_records[cur_date]["material_issues"].append(iss_dict)
                        day_records[cur_date]["stock_movements"].append(mov_out_dict)
                        current_stock[m_id] -= actual_qty

                    # Finished goods stock movement IN
                    mov_in_id = next_ids["mov"]
                    next_ids["mov"] += 1
                    mov_in_dict = {
                        "id": mov_in_id,
                        "item_id": item_by_product[p_id].id,
                        "date": cur_date.strftime("%Y-%m-%d"),
                        "movement_type": "IN",
                        "quantity": actual_qty,
                        "goods_receipt_line_id": None,
                        "material_issue_id": None,
                        "production_order_id": prod_id,
                        "delivery_line_id": None
                    }
                    day_records[cur_date]["stock_movements"].append(mov_in_dict)
                    current_stock[p_id] += actual_qty

                print(f"Production {prod_id} for Product {p_id}: {actual_qty}/{batch_size} [{prod_status}]. Stock: {current_stock[p_id]}")

        # 5. Deliveries
        # On Jan 9 and 10, deliver finished goods built on Jan 8/9
        if d_num in (9, 10) and current_stock[201] >= 20:
            deliv_id = next_ids["deliv"]
            dell_id = next_ids["dell"]
            mov_del_id = next_ids["mov"]
            next_ids["deliv"] += 1
            next_ids["dell"] += 1
            next_ids["mov"] += 1

            shipped = 20
            deliv_dict = {
                "id": deliv_id,
                "sales_order_id": 231,  # Day 1 sales order
                "ship_date": cur_date.strftime("%Y-%m-%d"),
                "delivery_date": cur_date.strftime("%Y-%m-%d"),
                "status": "Delivered"
            }
            dell_dict = {
                "id": dell_id,
                "delivery_id": deliv_id,
                "sales_order_line_id": 231,
                "product_id": 201,
                "quantity_shipped": shipped
            }
            mov_del_dict = {
                "id": mov_del_id,
                "item_id": item_by_product[201].id,
                "date": cur_date.strftime("%Y-%m-%d"),
                "movement_type": "OUT",
                "quantity": shipped,
                "goods_receipt_line_id": None,
                "material_issue_id": None,
                "production_order_id": None,
                "delivery_line_id": dell_id
            }
            day_records[cur_date]["deliveries"].append(deliv_dict)
            day_records[cur_date]["delivery_lines"].append(dell_dict)
            day_records[cur_date]["stock_movements"].append(mov_del_dict)
            current_stock[201] -= shipped
            print(f"Shipped {shipped} units of Product 201 against sales order 231.")

    # Insert all generated rows into sage_ext
    print("\nInserting all 10 days of operational records into sage_ext...")
    for d_num in range(1, 11):
        cur_date = date(2026, 1, d_num)
        recs = day_records[cur_date]
        for tbl in ["purchase_orders", "purchase_order_lines", "goods_receipts", "goods_receipt_lines",
                    "production_orders", "material_issues", "sales_orders", "sales_order_lines",
                    "deliveries", "delivery_lines", "stock_movements"]:
            rows = recs[tbl]
            if rows:
                cols = EXPECTED_COLUMNS[tbl]
                col_str = ", ".join(cols)
                val_str = ", ".join([f":{c}" for c in cols])
                db.execute(text(f"INSERT INTO {tbl} ({col_str}) VALUES ({val_str})"), rows)
    db.commit()
    print("Database committed on sage_ext.")

    # Export packs to demo_data/packs/ and demo_data/queue/
    print("\nExporting day packs to demo_data/packs/ and demo_data/queue/...")
    PACKS_DIR.mkdir(parents=True, exist_ok=True)
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)

    # Clean old packs
    for old_dir in PACKS_DIR.glob("*"):
        if old_dir.is_dir():
            shutil.rmtree(old_dir)
    for old_dir in QUEUE_DIR.glob("*"):
        if old_dir.is_dir():
            shutil.rmtree(old_dir)

    for d_num in range(1, 11):
        cur_date = date(2026, 1, d_num)
        date_str = cur_date.strftime("%Y-%m-%d")
        pack_path = PACKS_DIR / date_str
        pack_path.mkdir(parents=True, exist_ok=True)

        recs = day_records[cur_date]
        row_counts = {}
        total_events = 0

        for tbl, cols in EXPECTED_COLUMNS.items():
            csv_path = pack_path / f"{tbl}.csv"
            rows = recs[tbl]
            row_counts[tbl] = len(rows)
            total_events += len(rows)
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=cols)
                writer.writeheader()
                for r in rows:
                    writer.writerow(r)

        meta = {
            "pack_date": date_str,
            "is_simulated": True,
            "label": "SIMULATED ERP OPERATIONAL PACK",
            "framing": FRAMING,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "row_counts": row_counts,
            "total_events": total_events
        }
        with open(pack_path / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        # Copy to queue
        queue_dest = QUEUE_DIR / date_str
        shutil.copytree(pack_path, queue_dest)
        print(f"Exported pack {date_str}: {total_events} events -> {pack_path.name}")

    db.close()
    print("\nAll 10 day packs exported and queued successfully.")


if __name__ == "__main__":
    run_demo_simulation()
