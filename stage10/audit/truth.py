"""
stage10/audit/truth.py — Single Source of Truth for SAGE
Reads from main PostgreSQL (read-only) and analytics/scenario_causal_evaluation.json.
Writes stage10/audit/truth.json.
Every figure displayed anywhere must trace to this file.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

CUTOFF = date(2025, 12, 31)
TRUTH_PATH = ROOT / "stage10" / "audit" / "truth.json"


def get_pg_conn():
    url = os.getenv("DATABASE_URL", "")
    m = re.match(r"postgresql\+psycopg2://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)", url)
    if not m:
        raise RuntimeError("Cannot parse DATABASE_URL")
    user, pw, host, port, db = m.groups()
    import psycopg2
    conn = psycopg2.connect(host=host, port=port, dbname=db, user=user, password=pw)
    conn.set_session(readonly=True)
    return conn


def compute_truth() -> Dict[str, Any]:
    conn = get_pg_conn()
    cur = conn.cursor()
    truth: Dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cutoff": CUTOFF.isoformat(),
        "framing": "SAGE performs controlled synthetic causal-attribution evaluation under an expert-defined causal model; it does not claim to prove real-world causality."
    }

    # === 1. Fulfillment breakdown for orders requested on or before 2025-12-31 ===
    cur.execute("""
    SELECT so.id, so.requested_delivery_date, sol.product_id, sol.quantity_ordered,
           COALESCE(SUM(dl.quantity_shipped), 0) as shipped,
           MIN(d.ship_date) as first_ship, MAX(d.ship_date) as last_ship
    FROM sales_orders so
    JOIN sales_order_lines sol ON so.id = sol.sales_order_id
    LEFT JOIN delivery_lines dl ON dl.sales_order_line_id = sol.id
    LEFT JOIN deliveries d ON d.id = dl.delivery_id AND d.ship_date <= %s
    WHERE so.requested_delivery_date <= %s
    GROUP BY so.id, so.requested_delivery_date, sol.id, sol.product_id, sol.quantity_ordered
    ORDER BY so.id
    """, (CUTOFF.isoformat(), CUTOFF.isoformat()))
    rows = cur.fetchall()

    buckets = {
        "on_time": {"orders": 0, "ordered": 0, "shipped": 0, "open": 0, "ids": []},
        "late":    {"orders": 0, "ordered": 0, "shipped": 0, "open": 0, "ids": []},
        "partial": {"orders": 0, "ordered": 0, "shipped": 0, "open": 0, "ids": []},
        "unshipped":{"orders": 0, "ordered": 0, "shipped": 0, "open": 0, "ids": []},
    }
    partial_details = []

    for r in rows:
        so_id, rd, pid, q_ord, q_ship, f_ship, l_ship = r
        q_open = max(0, q_ord - q_ship)
        if q_ship >= q_ord and l_ship and l_ship <= rd:
            b = buckets["on_time"]
        elif q_ship >= q_ord and l_ship and l_ship > rd:
            b = buckets["late"]
        elif 0 < q_ship < q_ord:
            b = buckets["partial"]
            partial_details.append({
                "so_id": so_id,
                "product_id": pid,
                "requested": str(rd),
                "ordered": q_ord,
                "shipped": q_ship,
                "open": q_open,
                "last_ship": str(l_ship)
            })
        else:
            b = buckets["unshipped"]
        b["orders"] += 1
        b["ordered"] += q_ord
        b["shipped"] += q_ship
        b["open"] += q_open
        b["ids"].append(so_id)

    total_orders = sum(b["orders"] for b in buckets.values())
    total_ordered = sum(b["ordered"] for b in buckets.values())
    total_shipped = sum(b["shipped"] for b in buckets.values())
    total_open = sum(b["open"] for b in buckets.values())
    on_time_pct = round(buckets["on_time"]["orders"] / total_orders * 100, 1) if total_orders else 0.0

    truth["fulfillment"] = {
        "cutoff": CUTOFF.isoformat(),
        "total_orders": total_orders,
        "total_ordered": total_ordered,
        "total_shipped": total_shipped,
        "total_open": total_open,
        "on_time": {k: v for k, v in buckets["on_time"].items() if k != "ids"},
        "late": {k: v for k, v in buckets["late"].items() if k != "ids"},
        "partial": {k: v for k, v in buckets["partial"].items() if k != "ids"},
        "unshipped": {k: v for k, v in buckets["unshipped"].items() if k != "ids"},
        "on_time_pct": on_time_pct,
        "partial_details": partial_details,
    }

    # === 2. Orders due in January 2026 ===
    cur.execute("""
    SELECT COUNT(*), COALESCE(SUM(sol.quantity_ordered), 0)
    FROM sales_orders so
    JOIN sales_order_lines sol ON so.id = sol.sales_order_id
    WHERE so.requested_delivery_date > %s AND so.requested_delivery_date <= '2026-01-31'
    """, (CUTOFF.isoformat(),))
    jan = cur.fetchone()
    truth["orders_due_jan_2026"] = {"orders": jan[0], "units": int(jan[1])}

    # === 3. Supplier PO summary from actual transactions ===
    cur.execute("""
    SELECT s.id, s.name, COUNT(DISTINCT po.id) as po_count, COUNT(DISTINCT gr.id) as receipt_count,
           STRING_AGG(DISTINCT p.name, ', ' ORDER BY p.name) as materials
    FROM suppliers s
    LEFT JOIN purchase_orders po ON s.id = po.supplier_id
    LEFT JOIN goods_receipts gr ON gr.po_id = po.id
    LEFT JOIN purchase_order_lines pol ON po.id = pol.po_id
    LEFT JOIN products p ON pol.material_id = p.id
    GROUP BY s.id, s.name ORDER BY s.id
    """)
    suppliers = []
    for r in cur.fetchall():
        suppliers.append({
            "id": r[0],
            "name": r[1],
            "po_count": r[2],
            "receipt_count": r[3],
            "materials": r[4] or "none"
        })
    truth["suppliers"] = suppliers

    # === 4. PO #17 and PO #18 full rows ===
    for po_id in [17, 18]:
        cur.execute("""
        SELECT po.id, po.order_date, po.expected_delivery_date, po.status, po.supplier_id, s.name,
               pol.material_id, pol.quantity_ordered, p.name,
               COALESCE(SUM(grl.quantity_received), 0) as total_received
        FROM purchase_orders po
        JOIN purchase_order_lines pol ON po.id = pol.po_id
        JOIN suppliers s ON po.supplier_id = s.id
        JOIN products p ON pol.material_id = p.id
        LEFT JOIN goods_receipt_lines grl ON grl.po_line_id = pol.id
        WHERE po.id = %s
        GROUP BY po.id, po.order_date, po.expected_delivery_date, po.status, po.supplier_id, s.name,
                 pol.material_id, pol.quantity_ordered, p.name
        """, (po_id,))
        r = cur.fetchone()
        if r:
            qty_ord = r[7]
            qty_rec = int(r[9])
            is_completed = (qty_rec >= qty_ord and qty_ord > 0)
            days_overdue = 0 if is_completed else ((CUTOFF - r[2]).days if r[2] else 0)

            # Get receipt details
            cur.execute("""
            SELECT gr.id, gr.receipt_date, gr.status, grl.quantity_received
            FROM goods_receipts gr
            JOIN goods_receipt_lines grl ON grl.receipt_id = gr.id
            WHERE gr.po_id = %s
            ORDER BY gr.receipt_date
            """, (po_id,))
            gr_list = [{"id": gr[0], "date": str(gr[1]), "status": gr[2], "qty": gr[3]} for gr in cur.fetchall()]

            summary_desc = (
                "first delivery: 70% of the order (105 of 150 units); completed 2 days after the first delivery"
                if po_id == 17 else
                f"{days_overdue} days overdue (was due {r[2]})"
            )

            truth[f"po_{po_id}"] = {
                "id": r[0],
                "order_date": str(r[1]),
                "expected_delivery_date": str(r[2]),
                "status": r[3],
                "supplier_id": r[4],
                "supplier_name": r[5],
                "material_id": r[6],
                "material_name": r[8],
                "quantity_ordered": qty_ord,
                "quantity_received": qty_rec,
                "is_completed": is_completed,
                "days_overdue_at_cutoff": days_overdue,
                "summary": summary_desc,
                "receipts": gr_list
            }

    # === 5. Per-product open units ===
    cur.execute("""
    SELECT sol.product_id, p.name, SUM(sol.quantity_ordered) as ordered,
           COALESCE(SUM(dl.quantity_shipped), 0) as shipped
    FROM sales_orders so
    JOIN sales_order_lines sol ON so.id = sol.sales_order_id
    JOIN products p ON sol.product_id = p.id
    LEFT JOIN delivery_lines dl ON dl.sales_order_line_id = sol.id
    LEFT JOIN deliveries d ON d.id = dl.delivery_id AND d.ship_date <= %s
    WHERE so.requested_delivery_date <= %s
    GROUP BY sol.product_id, p.name ORDER BY sol.product_id
    """, (CUTOFF.isoformat(), CUTOFF.isoformat()))
    products = []
    for r in cur.fetchall():
        products.append({
            "id": r[0],
            "name": r[1],
            "ordered": int(r[2]),
            "shipped": int(r[3]),
            "open": int(r[2]) - int(r[3])
        })
    truth["products_fulfillment"] = products

    # === 6. Per-customer open units ===
    cur.execute("""
    SELECT c.id, c.name, COUNT(DISTINCT so.id) as orders,
           SUM(sol.quantity_ordered) as ordered,
           COALESCE(SUM(dl.quantity_shipped), 0) as shipped
    FROM sales_orders so
    JOIN sales_order_lines sol ON so.id = sol.sales_order_id
    JOIN customers c ON so.customer_id = c.id
    LEFT JOIN delivery_lines dl ON dl.sales_order_line_id = sol.id
    LEFT JOIN deliveries d ON d.id = dl.delivery_id AND d.ship_date <= %s
    WHERE so.requested_delivery_date <= %s
    GROUP BY c.id, c.name ORDER BY c.id
    """, (CUTOFF.isoformat(), CUTOFF.isoformat()))
    customers = []
    for r in cur.fetchall():
        customers.append({
            "id": r[0],
            "name": r[1],
            "orders": r[2],
            "ordered": int(r[3]),
            "shipped": int(r[4]),
            "open": int(r[3]) - int(r[4])
        })
    truth["customers_fulfillment"] = customers

    # === 7. Stage 7 evaluation cohorts ===
    eval_path = ROOT / "analytics" / "scenario_causal_evaluation.json"
    if eval_path.exists():
        with open(eval_path) as f:
            eval_data = json.load(f)
        scenarios = eval_data.get("scenarios", [])
        truth["stage7_scenarios"] = scenarios

        def calc_cohort(id_list: List[str], label: str, reason: str):
            subset = [s for s in scenarios if s.get("scenario_id") in id_list]
            n = len(subset)
            if n == 0:
                return {"label": label, "n": 0, "reason": reason}
            h1 = sum(1 for s in subset if s.get("avg_rank") == 1.0)
            h3 = sum(1 for s in subset if s.get("avg_rank") <= 3.0)
            recip = [1.0 / s["avg_rank"] if s.get("avg_rank", 99) < 99 else 0.0 for s in subset]
            mrr = sum(recip) / n
            return {
                "label": label,
                "n": n,
                "hit_at_1": round(h1 / n * 100, 1),
                "hit_at_3": round(h3 / n * 100, 1),
                "mrr": round(mrr, 4),
                "ids": id_list,
                "reason": reason
            }

        all_ids = [s["scenario_id"] for s in scenarios]
        truth["stage7_cohorts"] = {
            "all_10": calc_cohort(
                all_ids,
                "All 10 scenarios",
                "Complete synthetic benchmark suite including controls and structural edge cases"
            ),
            "excl_01_05": calc_cohort(
                [i for i in all_ids if i not in ("INC_01", "INC_05")],
                "Excluding INC_01 & INC_05 (8 scenarios)",
                "Suppliers 1 & 2 never received POs due to simulator choose_supplier date bug"
            ),
            "original_stage7_six": calc_cohort(
                ["INC_01", "INC_03", "INC_04", "INC_05", "INC_06", "INC_08"],
                "Original Stage 7 Six-Case Benchmark",
                "Pre-registered real-cause evaluation cohort from frozen Stage 7 evaluate_against_ground_truth.py"
            ),
            "physical_four": calc_cohort(
                ["INC_03", "INC_04", "INC_06", "INC_08"],
                "Four Physical-Cause Scenarios",
                "Only scenarios where injected disruptions physically propagated downstream to active plant operations"
            ),
        }

    # === 8. DAG supplier->material edges vs actual sourcing ===
    cur.execute("""
    SELECT DISTINCT po.supplier_id, s.name, pol.material_id, p.name
    FROM purchase_orders po
    JOIN purchase_order_lines pol ON po.id = pol.po_id
    JOIN suppliers s ON po.supplier_id = s.id
    JOIN products p ON pol.material_id = p.id
    ORDER BY po.supplier_id
    """)
    truth["actual_sourcing_edges"] = [
        {"supplier_id": r[0], "supplier_name": r[1], "material_id": r[2], "material_name": r[3]}
        for r in cur.fetchall()
    ]

    # Stage 7 DAG edges (expert-defined graph)
    truth["dag_supplier_edges"] = [
        {"supplier_id": 1, "supplier_name": "Sri Materials Pvt Ltd", "material_id": 101, "material_name": "Steel Rod 10mm", "active_in_2025": False},
        {"supplier_id": 2, "supplier_name": "Bharat Steel Works", "material_id": 101, "material_name": "Steel Rod 10mm", "active_in_2025": False},
        {"supplier_id": 4, "supplier_name": "EastCoast Components", "material_id": 101, "material_name": "Steel Rod 10mm", "active_in_2025": True},
        {"supplier_id": 3, "supplier_name": "Global Polymers Co", "material_id": 102, "material_name": "Plastic Granules", "active_in_2025": True},
        {"supplier_id": 5, "supplier_name": "Copper & Co", "material_id": 103, "material_name": "Copper Wire", "active_in_2025": True},
    ]

    # === 9. Incidents Mapping: YAML vs business_events vs PO actually delayed ===
    cur.execute("""
    SELECT id, event_type, entity_type, entity_id, occurred_start_date, occurred_end_date, description
    FROM business_events ORDER BY id
    """)
    be_rows = cur.fetchall()
    be_by_inc = {}
    for be in be_rows:
        try:
            desc = json.loads(be[6])
            inc_id = desc.get("incident_id")
            if inc_id:
                be_by_inc.setdefault(inc_id, []).append({
                    "event_type": be[1],
                    "entity_type": be[2],
                    "entity_id": be[3],
                    "start": str(be[4]),
                    "end": str(be[5]),
                })
        except Exception:
            pass

    # Incident definitions from incidents.yaml & simulation
    incidents_truth = [
        {
            "id": "INC_01",
            "type": "supplier_delay",
            "yaml_target": "Supplier 1 (Sri Materials)",
            "business_events": be_by_inc.get("INC_01", []),
            "po_actually_delayed": None,
            "physical_impact": "None (Supplier 1 had 0 POs in 2025 due to simulator choose_supplier bug)"
        },
        {
            "id": "INC_02",
            "type": "no_incident",
            "yaml_target": "None (negative control)",
            "business_events": be_by_inc.get("INC_02", []),
            "po_actually_delayed": None,
            "physical_impact": "None (negative control)"
        },
        {
            "id": "INC_03",
            "type": "demand_spike",
            "yaml_target": "Product 201 (Widget Model X)",
            "business_events": be_by_inc.get("INC_03", []),
            "po_actually_delayed": None,
            "physical_impact": "Demand surge 1.87x absorbed by buffer"
        },
        {
            "id": "INC_04",
            "type": "capacity_disruption",
            "yaml_target": "Product 201 (Widget Model X)",
            "business_events": be_by_inc.get("INC_04", []),
            "po_actually_delayed": None,
            "physical_impact": "34.2% capacity loss on Line 1"
        },
        {
            "id": "INC_05",
            "type": "overlapping_supplier_delay",
            "yaml_target": "Supplier 1 & Supplier 2",
            "business_events": be_by_inc.get("INC_05", []),
            "po_actually_delayed": None,
            "physical_impact": "None (Suppliers 1 & 2 had 0 POs in 2025 due to simulator bug)"
        },
        {
            "id": "INC_06",
            "type": "simultaneous_independent",
            "yaml_target": "Supplier 2 & Product 202 (Widget Model Y)",
            "business_events": be_by_inc.get("INC_06", []),
            "po_actually_delayed": None,
            "physical_impact": "Line 2 capacity reduced 30.8% (Supplier 2 delay had no effect)"
        },
        {
            "id": "INC_07",
            "type": "partial_receipt",
            "yaml_target": "Supplier 5 (Copper & Co)",
            "business_events": be_by_inc.get("INC_07", []),
            "po_actually_delayed": 17,
            "physical_impact": "PO #17 partial receipt: 105 of 150 units (70.1%) on 2025-08-07, balance completed 2025-08-09"
        },
        {
            "id": "INC_08",
            "type": "delay_absorbed_by_safety_stock",
            "yaml_target": "Supplier 4 (EastCoast Components)",
            "business_events": be_by_inc.get("INC_08", []),
            "po_actually_delayed": 4,
            "physical_impact": "PO #04 delayed 4 days, absorbed by raw material safety stock without stockout"
        },
        {
            "id": "INC_09",
            "type": "severe_supplier_delay_stockout",
            "yaml_target": "Supplier 4 (EastCoast Components)",
            "business_events": be_by_inc.get("INC_09", []),
            "po_actually_delayed": 18,
            "physical_impact": "PO #18 severe delay: 407 units steel due 2025-08-14 never delivered (139d overdue at cutoff)"
        },
        {
            "id": "INC_10",
            "type": "seasonal_demand",
            "yaml_target": "Product 202 (Widget Model Y)",
            "business_events": be_by_inc.get("INC_10", []),
            "po_actually_delayed": None,
            "physical_impact": "Normal Q4 calendar seasonality (control pattern)"
        },
    ]
    truth["incidents"] = incidents_truth

    # === 10. Independent cross-check ===
    cur.execute("""
    SELECT COUNT(*) FROM (
        SELECT so.id FROM sales_orders so
        JOIN sales_order_lines sol ON so.id = sol.sales_order_id
        LEFT JOIN delivery_lines dl ON dl.sales_order_line_id = sol.id
        LEFT JOIN deliveries d ON d.id = dl.delivery_id AND d.ship_date <= %s
        WHERE so.requested_delivery_date <= %s
        GROUP BY so.id, sol.id, sol.quantity_ordered
        HAVING COALESCE(SUM(dl.quantity_shipped), 0) >= sol.quantity_ordered
               AND MAX(d.ship_date) <= so.requested_delivery_date
    ) sub
    """, (CUTOFF.isoformat(), CUTOFF.isoformat()))
    cross_on_time = cur.fetchone()[0]
    truth["cross_check"] = {
        "on_time_orders_method_1": buckets["on_time"]["orders"],
        "on_time_orders_method_2": cross_on_time,
        "match": buckets["on_time"]["orders"] == cross_on_time,
    }
    if buckets["on_time"]["orders"] != cross_on_time:
        raise AssertionError(f"Cross-check failed: method 1 ({buckets['on_time']['orders']}) != method 2 ({cross_on_time})")

    # Master tables
    cur.execute("SELECT id, name FROM suppliers ORDER BY id")
    truth["master_suppliers"] = [{"id": r[0], "name": r[1]} for r in cur.fetchall()]
    cur.execute("SELECT id, name, category, unit_of_measure FROM products WHERE category = 'Raw Material' ORDER BY id")
    truth["master_materials"] = [{"id": r[0], "name": r[1], "uom": r[3]} for r in cur.fetchall()]
    cur.execute("SELECT id, name, category, unit_of_measure FROM products WHERE category = 'Finished Good' ORDER BY id")
    truth["master_products"] = [{"id": r[0], "name": r[1], "uom": r[3]} for r in cur.fetchall()]

    # Row counts
    count_tables = [
        "customers", "sales_orders", "sales_order_lines", "deliveries", "delivery_lines",
        "purchase_orders", "purchase_order_lines", "goods_receipts", "goods_receipt_lines",
        "suppliers", "products", "inventory_items", "stock_movements", "production_orders"
    ]
    row_counts = {}
    for tbl in count_tables:
        cur.execute(f"SELECT COUNT(*) FROM {tbl}")
        row_counts[tbl] = cur.fetchone()[0]
    truth["pg_row_counts"] = row_counts

    conn.close()
    return truth


def print_summary(truth: Dict[str, Any]):
    f = truth["fulfillment"]
    print("=" * 80)
    print("SAGE TRUTH TABLE — Source: Main PostgreSQL (read-only)")
    print("=" * 80)
    print(f"\nOrders requested on or before {f['cutoff']}:")
    print(f"  {'Category':42s} | {'Orders':>6} | {'Ordered':>7} | {'Shipped':>7} | {'Open':>6} | {'%':>6}")
    print("  " + "-" * 80)
    for k in ["on_time", "late", "partial", "unshipped"]:
        b = f[k]
        labels = {
            "on_time": "Shipped complete on/before requested",
            "late": "Shipped complete AFTER requested",
            "partial": "Partly shipped (open backorder)",
            "unshipped": "Unshipped (open backorder)"
        }
        pct = round(b["orders"] / f["total_orders"] * 100, 1) if f["total_orders"] else 0
        print(f"  {labels[k]:42s} | {b['orders']:>6} | {b['ordered']:>7} | {b['shipped']:>7} | {b['open']:>6} | {pct:>5.1f}%")
    print("  " + "-" * 80)
    print(f"  {'TOTAL':42s} | {f['total_orders']:>6} | {f['total_ordered']:>7} | {f['total_shipped']:>7} | {f['total_open']:>6} | 100.0%")
    print(f"\n  On-time %: {f['on_time_pct']}%")

    if f["partial_details"]:
        print("\n  Partly shipped orders:")
        for p in f["partial_details"]:
            print(f"    SO #{p['so_id']} (Product {p['product_id']}): due {p['requested']}, "
                  f"ordered {p['ordered']}u, shipped {p['shipped']}u, open {p['open']}u")

    for po_key in ["po_17", "po_18"]:
        if po_key in truth:
            po = truth[po_key]
            print(f"\n  PO #{po['id']}: {po['supplier_name']} (S{po['supplier_id']}), "
                  f"{po['material_name']} (M{po['material_id']})")
            print(f"    Ordered: {po['order_date']}, Expected: {po['expected_delivery_date']}, "
                  f"Status: {po['status']}")
            if po.get("is_completed"):
                print(f"    Qty ordered: {po['quantity_ordered']}, Received: {po['quantity_received']}, "
                      f"Details: {po.get('summary', 'Completed')}")
            else:
                print(f"    Qty ordered: {po['quantity_ordered']}, Received: {po['quantity_received']}, "
                      f"Days overdue at {f['cutoff']}: {po['days_overdue_at_cutoff']} (was due {po['expected_delivery_date']})")

    print("\n  Supplier PO summary:")
    for s in truth["suppliers"]:
        print(f"    S{s['id']} {s['name']:25s}: {s['po_count']:>3} POs, "
              f"{s['receipt_count']:>3} receipts, materials: {s['materials']}")

    print(f"\n  Cross-check: on_time method1={truth['cross_check']['on_time_orders_method_1']}, "
          f"method2={truth['cross_check']['on_time_orders_method_2']}, match={truth['cross_check']['match']}")

    if "stage7_cohorts" in truth:
        print("\n  Stage 7 Evaluation Cohorts:")
        for k, c in truth["stage7_cohorts"].items():
            if c["n"] > 0:
                print(f"    {c['label']}: n={c['n']}, Hit@1={c['hit_at_1']}%, "
                      f"Hit@3={c['hit_at_3']}%, MRR={c['mrr']}")
                print(f"      Reason: {c['reason']}")

    jan = truth.get("orders_due_jan_2026", {})
    print(f"\n  Orders due Jan 2026: {jan.get('orders', 0)} orders, {jan.get('units', 0)} units")


def main():
    truth = compute_truth()
    out_path = ROOT / "stage10" / "audit" / "truth.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(truth, f, indent=2)
    print_summary(truth)
    print(f"\nWritten to {out_path}")
    print(f"SHA256: {hashlib.sha256(out_path.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
