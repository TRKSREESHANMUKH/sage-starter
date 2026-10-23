"""
stage10/audit/orders_audit.py — Definitive Customer Orders Audit
Reads strictly from stage10/audit/truth.json (generated from main PostgreSQL).
NO HARDCODED NUMBERS OR STATIC ORDER IDS.
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

    ful = truth["fulfillment"]
    print("=" * 80)
    print("SAGE CUSTOMER ORDERS FORENSIC RECONCILIATION AUDIT (orders_audit.py)")
    print(f"Source: Main PostgreSQL (as of {ful['cutoff']})")
    print("=" * 80)

    print(f"\nTABLE: FULFILLMENT BREAKDOWN FOR ALL {ful['total_orders']} ORDERS REQUESTED <= {ful['cutoff']}\n")
    header = f"{'Fulfillment Category':<42} | {'Orders':<7} | {'Ordered':<8} | {'Shipped':<8} | {'Open':<8} | {'% Orders':<8}"
    print(header)
    print("-" * len(header))

    categories = [
        ("on_time", "Shipped complete on/before requested date"),
        ("late", "Shipped complete AFTER requested date"),
        ("partial", "Partly shipped (open backorder)"),
        ("unshipped", "Unshipped (open backorder)")
    ]

    for key, name in categories:
        b = ful[key]
        pct = (b["orders"] / ful["total_orders"] * 100.0) if ful["total_orders"] > 0 else 0.0
        print(f"{name:<42} | {b['orders']:<7} | {b['ordered']:<8} | {b['shipped']:<8} | {b['open']:<8} | {pct:>6.1f}%")

    print("-" * len(header))
    tot_shipped = ful["total_shipped"]
    tot_open = ful["total_open"]
    print(f"{'GRAND TOTAL':<42} | {ful['total_orders']:<7} | {ful['total_ordered']:<8} | {tot_shipped:<8} | {tot_open:<8} | 100.0%\n")

    print(f"ON-TIME DELIVERY RATE: {ful['on_time_pct']}%\n")

    print("PARTLY SHIPPED ORDERS DETAIL:")
    for p in ful.get("partial_details", []):
        print(f"  * SO #{p['so_id']} (Product {p['product_id']}): Due {p['requested']}, "
              f"Ordered {p['ordered']}u, Shipped {p['shipped']}u on {p['last_ship']}, Open {p['open']}u backlog")

    jan = truth.get("orders_due_jan_2026", {})
    print(f"\nORDERS DUE IN JANUARY 2026 (AFTER {ful['cutoff']}):")
    print(f"  * Order count: {jan.get('orders', 0)}")
    print(f"  * Units count: {jan.get('units', 0)}")

    cc = truth.get("cross_check", {})
    print(f"\nINDEPENDENT CROSS-CHECK:")
    print(f"  * Method 1 (Fulfillment classifier) : {cc.get('on_time_orders_method_1')}")
    print(f"  * Method 2 (Direct SQL HAVING check): {cc.get('on_time_orders_method_2')}")
    print(f"  * Verified Match                     : {cc.get('match')}")
    print("=" * 80)


if __name__ == "__main__":
    run_audit()
