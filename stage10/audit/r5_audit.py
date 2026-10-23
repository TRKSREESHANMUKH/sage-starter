"""
stage10/audit/r5_audit.py — R5 Sourcing, DAG Edges & Synthetic Incidents Audit
Reads strictly from stage10/audit/truth.json (generated from main PostgreSQL).
NO HARDCODED NUMBERS OR STATIC CLAIMS.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
TRUTH_PATH = ROOT_DIR / "stage10" / "audit" / "truth.json"


def run_audit():
    if not TRUTH_PATH.exists():
        from stage10.audit.truth import main as generate_truth
        generate_truth()

    with open(TRUTH_PATH, "r", encoding="utf-8") as f:
        truth = json.load(f)

    print("=" * 95)
    print("SAGE R5 AUDIT: STAGE 7 DAG EDGES VS ACTUAL SOURCING VS SYNTHETIC INCIDENTS")
    print(f"Source: Main PostgreSQL (as of {truth['cutoff']})")
    print("=" * 95)

    print("\nPART 1: STAGE 7 EXPERT DAG SUPPLIER EDGES VS 2025 ACTUAL SOURCING")
    header_dag = f"{'Supplier ID & Name':<28} | {'Material Sourced':<22} | {'2025 Sourcing Status':<22} | {'PO Count':<8}"
    print(header_dag)
    print("-" * len(header_dag))

    supp_map = {s["id"]: s for s in truth.get("suppliers", [])}
    for e in truth.get("dag_supplier_edges", []):
        sid = e["supplier_id"]
        s_name = e["supplier_name"]
        m_name = e["material_name"]
        s_info = supp_map.get(sid, {})
        po_cnt = s_info.get("po_count", 0)
        status_str = "ACTIVE (Sourced in 2025)" if po_cnt > 0 else "IDLE BACKUP (0 Orders)"
        print(f"S{sid} {s_name:<25} | {m_name:<22} | {status_str:<22} | {po_cnt:<8}")

    print("-" * len(header_dag))

    print("\nPART 2: SYNTHETIC INCIDENTS (INC_01 TO INC_10) VS SOURCING REALITY")
    header_inc = f"{'Incident':<8} | {'Type':<22} | {'Target Entity':<24} | {'Delayed PO':<12} | {'Physical Plant Impact':<36}"
    print(header_inc)
    print("-" * 110)

    for inc in truth.get("incidents", []):
        iid = inc["id"]
        itype = inc["type"]
        target = inc["yaml_target"]
        po_del = f"PO #{inc['po_actually_delayed']}" if inc.get("po_actually_delayed") else "None"
        impact = inc.get("physical_impact", "")
        print(f"{iid:<8} | {itype:<22} | {target:<24} | {po_del:<12} | {impact[:36]:<36}")

    print("-" * 110)

    print("\nPART 3: AUDITED VENDOR ACCOUNTS")
    for s in truth.get("suppliers", []):
        print(f"  * Supplier {s['id']}: {s['name']} — {s['po_count']} POs placed, {s['receipt_count']} receipts, materials: {s['materials']}")

    for po_id in [17, 18]:
        po_key = f"po_{po_id}"
        if po_key in truth:
            po = truth[po_key]
            print(f"\n  * Purchase Order #{po['id']} Detail:")
            print(f"      Vendor        : {po['supplier_name']} (Supplier ID {po['supplier_id']})")
            print(f"      Material      : {po['material_name']} (Material ID {po['material_id']})")
            print(f"      Order Date    : {po['order_date']}")
            print(f"      Expected Date : {po['expected_delivery_date']}")
            print(f"      Status in DB  : {po['status']}")
            print(f"      Ordered Qty   : {po['quantity_ordered']}")
            print(f"      Received Qty  : {po['quantity_received']}")
            print(f"      Days Overdue  : {po['days_overdue_at_cutoff']} days (as of {truth['cutoff']})")
            for gr in po.get("receipts", []):
                print(f"      - Receipt #{gr['id']}: {gr['qty']} units on {gr['date']} (status: {gr['status']})")

    print("=" * 95)


if __name__ == "__main__":
    run_audit()
