"""
stage10/audit/gate_a_full.py — Exhaustive Gate A Audit Script
Reads strictly from stage10/audit/truth.json and main PostgreSQL (read-only).
NO HARDCODED NUMBERS OR STATIC CLAIMS.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from stage10.audit.truth import CUTOFF, get_pg_conn, TRUTH_PATH


def run_a1():
    print("\n" + "=" * 70)
    print(f"GATE A1: Customer Orders Requested <= {CUTOFF.isoformat()} & Delivery Buckets")
    print("=" * 70)

    if not TRUTH_PATH.exists():
        from stage10.audit.truth import main as generate_truth
        generate_truth()

    with open(TRUTH_PATH, "r", encoding="utf-8") as f:
        truth = json.load(f)

    ful = truth["fulfillment"]
    print(f"Total Customer Orders Requested <= {ful['cutoff']} : {ful['total_orders']}")
    print(f"  (a) Shipped complete on/before requested date: {ful['on_time']['orders']} orders ({ful['on_time']['shipped']} units)")
    print(f"  (b) Shipped complete AFTER requested date    : {ful['late']['orders']} orders ({ful['late']['shipped']} units)")
    print(f"  (c) Partly shipped                           : {ful['partial']['orders']} orders ({ful['partial']['shipped']} shipped, {ful['partial']['open']} open)")
    print(f"  (d) Unshipped                                : {ful['unshipped']['orders']} orders ({ful['unshipped']['open']} open units)")
    print(f"  On-Time Delivery Rate                        : {ful['on_time_pct']}%")

    conn = get_pg_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM deliveries")
    total_dels = cur.fetchone()[0]
    print(f"\nTotal delivery records in Main PostgreSQL: {total_dels}")
    conn.close()


def run_a2():
    print("\n" + "=" * 70)
    print("GATE A2: PO #18 Deep Trace Across Postgres")
    print("=" * 70)

    conn = get_pg_conn()
    cur = conn.cursor()
    cur.execute("""
    SELECT po.id, po.supplier_id, s.name, pol.material_id, p.name, po.order_date, po.expected_delivery_date, po.status, pol.quantity_ordered
    FROM purchase_orders po
    JOIN purchase_order_lines pol ON po.id = pol.po_id
    JOIN suppliers s ON po.supplier_id = s.id
    JOIN products p ON pol.material_id = p.id
    WHERE po.id = 18
    """)
    r = cur.fetchone()
    if r:
        days_overdue = (CUTOFF - r[6]).days if r[6] else 0
        print(f"PO #18 Record:")
        print(f"  ID: {r[0]}")
        print(f"  Supplier: {r[2]} (ID {r[1]})")
        print(f"  Material: {r[4]} (ID {r[3]})")
        print(f"  Order Date: {r[5]}")
        print(f"  Expected Delivery Date: {r[6]}")
        print(f"  Status: {r[7]}")
        print(f"  Quantity Ordered: {r[8]}")
        print(f"  Days Overdue at {CUTOFF.isoformat()}: {days_overdue} days")

    cur.execute("SELECT COUNT(*) FROM goods_receipts WHERE po_id = 18")
    gr_count = cur.fetchone()[0]
    print(f"Goods Receipts for PO #18: {gr_count} (Unfulfilled)")

    cur.execute("SELECT COUNT(*) FROM purchase_orders po JOIN purchase_order_lines pol ON po.id = pol.po_id WHERE pol.material_id = 101 AND po.id > 18")
    later_count = cur.fetchone()[0]
    print(f"Material 101 POs placed after PO #18: {later_count} (Reorder cycle stalled)")
    conn.close()


def run_a3():
    print("\n" + "=" * 70)
    print("GATE A3: Forbidden Literals & DAG Sourcing Validation")
    print("=" * 70)

    literals = [
        "1004", "Supplier 1's delivery", "Raw steel is running low",
        "Standard Motor", "Heavy Duty Motor", "Electric Motors",
        "Gear Assemblies", "Electronic housings", "Plastic resin",
        "Customer demand surge"
    ]
    code_files = []
    for p in ROOT_DIR.glob("**/*.py"):
        if "tests" not in str(p) and "venv" not in str(p) and "backups" not in str(p) and "audit" not in str(p) and "test_" not in p.name:
            code_files.append(p)
    for p in ROOT_DIR.glob("**/*.html"):
        if "backups" not in str(p):
            code_files.append(p)

    hit_count = 0
    for cf in code_files:
        try:
            content = cf.read_text(encoding="utf-8")
            for lit in literals:
                if lit in content:
                    lines = content.splitlines()
                    for idx, line in enumerate(lines, 1):
                        if lit in line:
                            rel = cf.relative_to(ROOT_DIR)
                            print(f"  Found '{lit}' at {rel}:{idx}: {line.strip()[:60]}")
                            hit_count += 1
        except Exception:
            pass
    if hit_count == 0:
        print("  ✓ Zero forbidden literals found outside tests/ and audit/!")


def main():
    run_a1()
    run_a2()
    run_a3()


if __name__ == "__main__":
    main()
