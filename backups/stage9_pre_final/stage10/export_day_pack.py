"""
stage10/export_day_pack.py — Daily Operational Event Pack Exporter.

Exports one day of ERP transactional events from the main PostgreSQL database
to demo_data/packs/<YYYY-MM-DD>/ as standardized CSV files:
- purchase_orders.csv
- purchase_order_lines.csv
- goods_receipts.csv
- goods_receipt_lines.csv
- sales_orders.csv
- sales_order_lines.csv
- deliveries.csv
- delivery_lines.csv
- production_orders.csv
- material_issues.csv
- stock_movements.csv
- metadata.json

Strict Anti-Leakage Rules:
1. Export ONLY rows whose event date equals the pack date.
2. Never export status or fulfillment fields computed from future events.
   - Initial PO status is 'OPEN' (or 'PLACED'), quantity_received = 0.
   - Initial SO status is 'OPEN', quantity_fulfilled = 0.
3. Every pack is explicitly labeled as simulated in metadata.json.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
PACKS_BASE_DIR = ROOT_DIR / "demo_data" / "packs"
RESEARCH_FRAMING = "SAGE performs controlled synthetic causal-attribution evaluation under an expert-defined causal model; it does not claim to prove real-world causality."


def get_pg_engine():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL not found in environment.")
    return create_engine(DATABASE_URL)


def export_day_pack(
    pack_date: date,
    out_dir: Optional[Path] = None,
    engine=None
) -> Path:
    """
    Exports a single day of operational events from PostgreSQL to out_dir / <YYYY-MM-DD>.
    Returns the path to the pack directory.
    """
    if engine is None:
        engine = get_pg_engine()

    d_str = pack_date.isoformat()
    target_dir = (out_dir or PACKS_BASE_DIR) / d_str
    target_dir.mkdir(parents=True, exist_ok=True)

    row_counts: Dict[str, int] = {}

    with engine.connect() as conn:
        # 1. Purchase Orders placed on pack_date
        q_pos = text("""
            SELECT id, supplier_id, order_date, expected_delivery_date, 'OPEN' AS status
            FROM purchase_orders
            WHERE order_date = :d
            ORDER BY id
        """)
        pos = conn.execute(q_pos, {"d": pack_date}).mappings().fetchall()
        _write_csv(target_dir / "purchase_orders.csv", pos, ["id", "supplier_id", "order_date", "expected_delivery_date", "status"])
        row_counts["purchase_orders"] = len(pos)

        po_ids = [p["id"] for p in pos]
        if po_ids:
            q_pols = text("""
                SELECT id, po_id, material_id, quantity_ordered, 0 AS quantity_received
                FROM purchase_order_lines
                WHERE po_id = ANY(:po_ids)
                ORDER BY id
            """)
            pols = conn.execute(q_pols, {"po_ids": po_ids}).mappings().fetchall()
        else:
            pols = []
        _write_csv(target_dir / "purchase_order_lines.csv", pols, ["id", "po_id", "material_id", "quantity_ordered", "quantity_received"])
        row_counts["purchase_order_lines"] = len(pols)

        # 2. Goods Receipts received on pack_date
        q_grs = text("""
            SELECT id, po_id, receipt_date, status
            FROM goods_receipts
            WHERE receipt_date = :d
            ORDER BY id
        """)
        grs = conn.execute(q_grs, {"d": pack_date}).mappings().fetchall()
        _write_csv(target_dir / "goods_receipts.csv", grs, ["id", "po_id", "receipt_date", "status"])
        row_counts["goods_receipts"] = len(grs)

        gr_ids = [g["id"] for g in grs]
        if gr_ids:
            q_grls = text("""
                SELECT id, receipt_id, po_line_id, material_id, quantity_received
                FROM goods_receipt_lines
                WHERE receipt_id = ANY(:gr_ids)
                ORDER BY id
            """)
            grls = conn.execute(q_grls, {"gr_ids": gr_ids}).mappings().fetchall()
        else:
            grls = []
        _write_csv(target_dir / "goods_receipt_lines.csv", grls, ["id", "receipt_id", "po_line_id", "material_id", "quantity_received"])
        row_counts["goods_receipt_lines"] = len(grls)

        # 3. Sales Orders placed on pack_date
        q_sos = text("""
            SELECT id, customer_id, order_date, requested_delivery_date, 'OPEN' AS status
            FROM sales_orders
            WHERE order_date = :d
            ORDER BY id
        """)
        sos = conn.execute(q_sos, {"d": pack_date}).mappings().fetchall()
        _write_csv(target_dir / "sales_orders.csv", sos, ["id", "customer_id", "order_date", "requested_delivery_date", "status"])
        row_counts["sales_orders"] = len(sos)

        so_ids = [s["id"] for s in sos]
        if so_ids:
            q_sols = text("""
                SELECT id, sales_order_id, product_id, quantity_ordered, 0 AS quantity_fulfilled
                FROM sales_order_lines
                WHERE sales_order_id = ANY(:so_ids)
                ORDER BY id
            """)
            sols = conn.execute(q_sols, {"so_ids": so_ids}).mappings().fetchall()
        else:
            sols = []
        _write_csv(target_dir / "sales_order_lines.csv", sols, ["id", "sales_order_id", "product_id", "quantity_ordered", "quantity_fulfilled"])
        row_counts["sales_order_lines"] = len(sols)

        # 4. Deliveries shipped on pack_date
        q_dels = text("""
            SELECT id, sales_order_id, ship_date, delivery_date, status
            FROM deliveries
            WHERE ship_date = :d
            ORDER BY id
        """)
        dels = conn.execute(q_dels, {"d": pack_date}).mappings().fetchall()
        _write_csv(target_dir / "deliveries.csv", dels, ["id", "sales_order_id", "ship_date", "delivery_date", "status"])
        row_counts["deliveries"] = len(dels)

        del_ids = [deliv["id"] for deliv in dels]
        if del_ids:
            q_dls = text("""
                SELECT id, delivery_id, sales_order_line_id, product_id, quantity_shipped
                FROM delivery_lines
                WHERE delivery_id = ANY(:del_ids)
                ORDER BY id
            """)
            dls = conn.execute(q_dls, {"del_ids": del_ids}).mappings().fetchall()
        else:
            dls = []
        _write_csv(target_dir / "delivery_lines.csv", dls, ["id", "delivery_id", "sales_order_line_id", "product_id", "quantity_shipped"])
        row_counts["delivery_lines"] = len(dls)

        # 5. Production Orders scheduled or executed on pack_date
        q_prods = text("""
            SELECT id, product_id, planned_start, planned_end, actual_start, actual_end, planned_qty, actual_qty, status
            FROM production_orders
            WHERE planned_start = :d
            ORDER BY id
        """)
        prods = conn.execute(q_prods, {"d": pack_date}).mappings().fetchall()
        _write_csv(target_dir / "production_orders.csv", prods, [
            "id", "product_id", "planned_start", "planned_end", "actual_start", "actual_end", "planned_qty", "actual_qty", "status"
        ])
        row_counts["production_orders"] = len(prods)

        prod_ids = [p["id"] for p in prods]
        if prod_ids:
            q_issues = text("""
                SELECT id, production_order_id, item_id, planned_quantity, planned_issue_date, quantity_issued, issue_date
                FROM material_issues
                WHERE production_order_id = ANY(:prod_ids)
                ORDER BY id
            """)
            issues = conn.execute(q_issues, {"prod_ids": prod_ids}).mappings().fetchall()
        else:
            issues = []
        _write_csv(target_dir / "material_issues.csv", issues, [
            "id", "production_order_id", "item_id", "planned_quantity", "planned_issue_date", "quantity_issued", "issue_date"
        ])
        row_counts["material_issues"] = len(issues)

        # 6. Stock Movements on pack_date
        q_moves = text("""
            SELECT id, item_id, date, movement_type, quantity, goods_receipt_line_id, material_issue_id, production_order_id, delivery_line_id
            FROM stock_movements
            WHERE date = :d
            ORDER BY id
        """)
        moves = conn.execute(q_moves, {"d": pack_date}).mappings().fetchall()
        _write_csv(target_dir / "stock_movements.csv", moves, [
            "id", "item_id", "date", "movement_type", "quantity",
            "goods_receipt_line_id", "material_issue_id", "production_order_id", "delivery_line_id"
        ])
        row_counts["stock_movements"] = len(moves)

    # 7. Metadata.json
    metadata = {
        "pack_date": d_str,
        "is_simulated": True,
        "label": "SIMULATED ERP OPERATIONAL PACK",
        "framing": RESEARCH_FRAMING,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "row_counts": row_counts,
        "total_events": sum(row_counts.values())
    }
    with open(target_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    return target_dir


def _write_csv(file_path: Path, rows: List[Dict[str, Any]], fieldnames: List[str]) -> None:
    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(dict(r))


def export_demo_packs() -> List[Path]:
    """
    Exports the 7 demo week packs (2025-02-03 to 2025-02-09) and the held-back pack (2025-02-10).
    """
    engine = get_pg_engine()
    exported: List[Path] = []
    # Demo week: 2025-02-03 through 2025-02-09
    start_d = date(2025, 2, 3)
    for offset in range(8):  # 0 to 7 -> 2025-02-03 to 2025-02-10
        cur_d = date.fromordinal(start_d.toordinal() + offset)
        p = export_day_pack(cur_d, engine=engine)
        exported.append(p)
        print(f"Exported pack {cur_d.isoformat()} -> {p}")
    return exported


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export daily operational event packs.")
    parser.add_argument("--date", help="Specific pack date (YYYY-MM-DD)")
    parser.add_argument("--all-demo-packs", action="store_true", help="Export 2025-02-03 to 2025-02-10")
    args = parser.parse_args()

    if args.all_demo_packs:
        export_demo_packs()
    elif args.date:
        d = datetime.strptime(args.date, "%Y-%m-%d").date()
        p = export_day_pack(d)
        print(f"Exported pack {d.isoformat()} -> {p}")
    else:
        export_demo_packs()
