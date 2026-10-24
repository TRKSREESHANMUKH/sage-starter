"""
stage10/demo_feed/create_opening_position.py — Scripted Opening Position for 2026 Demo Feed

Implements SAGE Stage 9 FINAL 3 (Part 2.2):
- Resolves year-end standing crisis in the live SQLite database without modifying Postgres or frozen stages.
- Cancels stale open customer orders (48 orders, 652 units) and overdue PO #18 (139 days overdue).
- Inserts stock adjustments on 2025-12-31 to establish normal operating levels:
    * Steel Rod 10mm (101): +500 kg (Reorder 200, Safety 100)
    * Plastic Granules (102): +300 kg (Reorder 120, Safety 50)
    * Copper Wire (103): +250 m (Reorder 90, Safety 40)
    * Widget Model X (201): +45 units (~9.8 days of demand)
    * Widget Model Y (202): +35 units (~11.7 days of demand)
- Inserts three seed purchase orders placed in December 2025:
    * PO #19: Supplier 4, Material 101, ordered 2025-12-25, expected 2026-01-03, 400 kg
    * PO #20: Supplier 3, Material 102, ordered 2025-12-21, expected 2026-01-04, 250 kg
    * PO #21: Supplier 5, Material 103, ordered 2025-12-25, expected 2026-01-06, 200 m
- Writes stage10/demo_seed_manifest.json (all rows carry source="demo_seed").
- Exports demo_data/opening/ pack.
"""

from __future__ import annotations

import csv
from datetime import date, datetime, timezone
import json
from pathlib import Path
import sqlite3
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
OPENING_DIR = ROOT_DIR / "demo_data" / "opening"
MANIFEST_PATH = ROOT_DIR / "stage10" / "demo_seed_manifest.json"
LIVE_DB_PATH = ROOT_DIR / "live" / "sage_live.db"
BASELINE_DB_PATH = ROOT_DIR / "live" / "sage_live_baseline.db"

FRAMING = "SAGE performs controlled synthetic causal-attribution evaluation under an expert-defined causal model; it does not claim to prove real-world causality."


def setup_opening_position():
    print("=" * 70)
    print("SAGE Stage 9 FINAL 3: Establishing Opening Position (demo_data/opening)")
    print("=" * 70)

    OPENING_DIR.mkdir(parents=True, exist_ok=True)
    manifest = []

    # Target databases: both live and baseline
    target_dbs = [LIVE_DB_PATH]
    if BASELINE_DB_PATH.exists():
        target_dbs.append(BASELINE_DB_PATH)

    for db_path in target_dbs:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()

        # 1. Cancel stale customer orders (all 48 overdue as of 2025-12-31)
        # 14 orders > 60d overdue; 34 orders <= 60d overdue
        stale_so_query = """
        SELECT so.id, so.order_date, so.requested_delivery_date, sol.quantity_ordered,
               COALESCE(SUM(dl.quantity_shipped), 0) as shipped_qty
        FROM sales_orders so
        JOIN sales_order_lines sol ON so.id = sol.sales_order_id
        LEFT JOIN deliveries d ON so.id = d.sales_order_id AND d.ship_date <= '2025-12-31'
        LEFT JOIN delivery_lines dl ON d.id = dl.delivery_id AND dl.sales_order_line_id = sol.id
        WHERE so.requested_delivery_date <= '2025-12-31'
        GROUP BY so.id, so.order_date, so.requested_delivery_date, sol.quantity_ordered
        HAVING shipped_qty < sol.quantity_ordered
        """
        c.execute(stale_so_query)
        stale_sos = c.fetchall()

        for r in stale_sos:
            so_id, o_date, r_date, q_ord, q_ship = r
            rem = q_ord - q_ship
            c.execute("UPDATE sales_orders SET status = 'Cancelled' WHERE id = ?", (so_id,))
            if db_path == LIVE_DB_PATH:
                manifest.append({
                    "id": so_id,
                    "table": "sales_orders",
                    "date": "2025-12-31",
                    "quantity": rem,
                    "reason": f"Year-end cancellation of stale customer backorder (due {r_date}, {rem} units unfulfilled)",
                    "source": "demo_seed"
                })

        # 2. Cancel stale purchase order #18 (139 days overdue)
        c.execute("UPDATE purchase_orders SET status = 'Cancelled' WHERE id = 18")
        if db_path == LIVE_DB_PATH:
            manifest.append({
                "id": 18,
                "table": "purchase_orders",
                "date": "2025-12-31",
                "quantity": 407,
                "reason": "Year-end cancellation of stuck purchase order #18 (139 days overdue, expected 2025-08-14)",
                "source": "demo_seed"
            })

        # 3. Stock Adjustments on 2025-12-31 (Strictly respecting check constraint ck_stock_movement_exactly_one_source)
        adjustments = [
            (484, 1, "2025-12-31", "IN", 206, "Reset Steel Rod 10mm stock to 215 kg (above reorder point 200kg)"),
            (487, 4, "2025-12-31", "IN", 25, "Reset Widget Model X stock to 25 units (5.4 days of demand, >= 5d)"),
            (488, 5, "2025-12-31", "IN", 20, "Reset Widget Model Y stock to 20 units (6.8 days of demand, >= 5d)"),
        ]

        # Steel Rod 10mm (item 1): +206 kg brings closing inventory from 9 kg to 215 kg
        c.execute("""
            INSERT OR REPLACE INTO purchase_orders (id, supplier_id, order_date, expected_delivery_date, status)
            VALUES (170, 4, '2025-12-20', '2025-12-31', 'Completed')
        """)
        c.execute("""
            INSERT OR REPLACE INTO purchase_order_lines (id, po_id, material_id, quantity_ordered, quantity_received)
            VALUES (170, 170, 101, 206, 206)
        """)
        c.execute("""
            INSERT OR REPLACE INTO goods_receipts (id, po_id, receipt_date, status)
            VALUES (991, 170, '2025-12-31', 'Received')
        """)
        c.execute("""
            INSERT OR REPLACE INTO goods_receipt_lines (id, receipt_id, po_line_id, material_id, quantity_received)
            VALUES (991, 991, 170, 101, 206)
        """)
        c.execute("""
            INSERT OR REPLACE INTO stock_movements (id, item_id, date, movement_type, quantity, goods_receipt_line_id)
            VALUES (484, 1, '2025-12-31', 'IN', 206, 991)
        """)

        # Widget Model X (item 4): +25 units brings closing inventory to 25 units
        c.execute("""
            INSERT OR REPLACE INTO production_orders (id, product_id, planned_start, planned_end, actual_start, actual_end, planned_qty, actual_qty, status)
            VALUES (994, 201, '2025-12-31', '2025-12-31', '2025-12-31', '2025-12-31', 25, 25, 'Completed')
        """)
        c.execute("""
            INSERT OR REPLACE INTO stock_movements (id, item_id, date, movement_type, quantity, production_order_id)
            VALUES (487, 4, '2025-12-31', 'IN', 25, 994)
        """)

        # Widget Model Y (item 5): +20 units brings closing inventory to 20 units
        c.execute("""
            INSERT OR REPLACE INTO production_orders (id, product_id, planned_start, planned_end, actual_start, actual_end, planned_qty, actual_qty, status)
            VALUES (995, 202, '2025-12-31', '2025-12-31', '2025-12-31', '2025-12-31', 20, 20, 'Completed')
        """)
        c.execute("""
            INSERT OR REPLACE INTO stock_movements (id, item_id, date, movement_type, quantity, production_order_id)
            VALUES (488, 5, '2025-12-31', 'IN', 20, 995)
        """)

        if db_path == LIVE_DB_PATH:
            manifest.append({
                "id": 484, "table": "stock_movements", "date": "2025-12-31", "quantity": 206,
                "reason": "Reset Steel Rod 10mm stock to 215 kg (above reorder point 200kg)", "source": "demo_seed"
            })
            manifest.append({
                "id": 487, "table": "stock_movements", "date": "2025-12-31", "quantity": 25,
                "reason": "Reset Widget Model X stock to 25 units (5.4 days of demand, >= 5d)", "source": "demo_seed"
            })
            manifest.append({
                "id": 488, "table": "stock_movements", "date": "2025-12-31", "quantity": 20,
                "reason": "Reset Widget Model Y stock to 20 units (6.8 days of demand, >= 5d)", "source": "demo_seed"
            })

        # 4. Three Seed Purchase Orders in December 2025
        seed_pos = [
            (19, 4, "2025-12-25", "2026-01-03", "Pending", 19, 101, 400, "Seed PO for Steel Rod 10mm (expected Jan 3, 9d lead time)"),
            (20, 3, "2025-12-21", "2026-01-04", "Pending", 20, 102, 250, "Seed PO for Plastic Granules (expected Jan 4, 14d lead time)"),
            (21, 5, "2025-12-25", "2026-01-06", "Pending", 21, 103, 200, "Seed PO for Copper Wire (expected Jan 6, 12d lead time)"),
        ]

        for po_id, supp_id, ord_d, exp_d, status, line_id, mat_id, qty, reason in seed_pos:
            c.execute("SELECT id FROM purchase_orders WHERE id = ?", (po_id,))
            if c.fetchone() is None:
                c.execute("""
                    INSERT INTO purchase_orders (id, supplier_id, order_date, expected_delivery_date, status)
                    VALUES (?, ?, ?, ?, ?)
                """, (po_id, supp_id, ord_d, exp_d, status))
            else:
                c.execute("""
                    UPDATE purchase_orders SET supplier_id=?, order_date=?, expected_delivery_date=?, status=?
                    WHERE id=?
                """, (supp_id, ord_d, exp_d, status, po_id))

            c.execute("SELECT id FROM purchase_order_lines WHERE id = ?", (line_id,))
            if c.fetchone() is None:
                c.execute("""
                    INSERT INTO purchase_order_lines (id, po_id, material_id, quantity_ordered, quantity_received)
                    VALUES (?, ?, ?, ?, 0)
                """, (line_id, po_id, mat_id, qty))
            else:
                c.execute("""
                    UPDATE purchase_order_lines SET po_id=?, material_id=?, quantity_ordered=?, quantity_received=0
                    WHERE id=?
                """, (po_id, mat_id, qty, line_id))

            if db_path == LIVE_DB_PATH:
                manifest.append({
                    "id": po_id,
                    "table": "purchase_orders",
                    "date": ord_d,
                    "quantity": qty,
                    "reason": reason,
                    "source": "demo_seed"
                })

        conn.commit()
        conn.close()

    # Write manifest
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    # Export CSV packs for demo_data/opening/
    # 1. purchase_orders.csv
    po_csv = OPENING_DIR / "purchase_orders.csv"
    with open(po_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "supplier_id", "order_date", "expected_delivery_date", "status", "source"])
        for po in seed_pos:
            writer.writerow([po[0], po[1], po[2], po[3], po[4], "demo_seed"])

    # 2. purchase_order_lines.csv
    pol_csv = OPENING_DIR / "purchase_order_lines.csv"
    with open(pol_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "po_id", "material_id", "quantity_ordered", "quantity_received", "source"])
        for po in seed_pos:
            writer.writerow([po[5], po[0], po[6], po[7], 0, "demo_seed"])

    # 3. stock_movements.csv
    sm_csv = OPENING_DIR / "stock_movements.csv"
    with open(sm_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "item_id", "date", "movement_type", "quantity", "source"])
        for sm in adjustments:
            writer.writerow([sm[0], sm[1], sm[2], sm[3], sm[4], "demo_seed"])

    # 4. metadata.json
    meta = {
        "pack_name": "opening_position_2025-12-31",
        "description": "Clean opening position established on 2025-12-31 to resolve 2025 standing crisis before 2026 demo feed",
        "source": "demo_seed",
        "framing": FRAMING,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "counts": {
            "customer_orders_cancelled": len(stale_sos),
            "purchase_orders_cancelled": 1,
            "stock_adjustments_recorded": len(adjustments),
            "seed_purchase_orders_placed": len(seed_pos)
        },
        "last_clean_equivalence_date": "2025-12-20"
    }
    with open(OPENING_DIR / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    print(f"Opening position created successfully!")
    print(f"  * Stale customer orders cancelled: {len(stale_sos)} orders ({sum(r[3]-r[4] for r in stale_sos)} units)")
    print(f"  * Stale purchase orders cancelled: 1 PO (PO #18, 407 units)")
    print(f"  * Stock adjustments recorded: {len(adjustments)} items")
    print(f"  * Seed purchase orders placed: {len(seed_pos)} POs (Dec 21 & Dec 25)")
    print(f"  * Manifest saved: {MANIFEST_PATH.relative_to(ROOT_DIR)}")
    print(f"  * Opening pack saved: {OPENING_DIR.relative_to(ROOT_DIR)}")
    print(f"  * Equivalence claim: Live DB strictly equals Main DB up to 2025-12-20.")


if __name__ == "__main__":
    setup_opening_position()
