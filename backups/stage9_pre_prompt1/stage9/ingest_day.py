"""
stage9/ingest_day.py — Operational Day Pack Ingestion Engine.

Part 2 Requirement:
- CLI: python -m stage9.ingest_day --pack demo_data/packs/<YYYY-MM-DD>
- Validates the pack:
    - All required CSVs and metadata.json exist.
    - Expected column headers present.
    - All date columns strictly equal the pack date (rejects past or future-dated rows).
    - No duplicate primary keys already present in live database.
- If validation fails, rejects whole pack with clear message and makes zero changes.
- Ingests all tables into live/sage_live.db within a single atomic transaction.
- Updates PO quantity_received and SO quantity_fulfilled based on incoming receipts/deliveries.
- Appends day to live daily panel.
- Updates stage9/state/current_day.json and writes stage9/state/ingest_log.jsonl.
- Invalidates analytics/insights_cache/.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd
from sqlalchemy import create_engine, text

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from stage9.current_day import register_ingested_day, set_current_day
from stage9.clock import set_replay_date

LIVE_DB_PATH = ROOT_DIR / "live" / "sage_live.db"
INGEST_LOG_PATH = ROOT_DIR / "stage9" / "state" / "ingest_log.jsonl"
INSIGHTS_CACHE_DIR = ROOT_DIR / "analytics" / "insights_cache"
PANEL_PARQUET_PATH = ROOT_DIR / "analytics" / "daily_panel.parquet"
LIVE_PANEL_PATH = ROOT_DIR / "analytics" / "daily_panel_live.parquet"

REQUIRED_FILES = [
    "metadata.json",
    "purchase_orders.csv",
    "purchase_order_lines.csv",
    "goods_receipts.csv",
    "goods_receipt_lines.csv",
    "sales_orders.csv",
    "sales_order_lines.csv",
    "deliveries.csv",
    "delivery_lines.csv",
    "production_orders.csv",
    "material_issues.csv",
    "stock_movements.csv"
]

EXPECTED_COLUMNS: Dict[str, List[str]] = {
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

DATE_COLUMNS: Dict[str, str] = {
    "purchase_orders": "order_date",
    "goods_receipts": "receipt_date",
    "sales_orders": "order_date",
    "deliveries": "ship_date",
    "production_orders": "planned_start",
    "stock_movements": "date"
}


class PackValidationError(ValueError):
    """Raised when an operational day pack fails validation."""
    pass


def validate_pack(pack_dir: Path, live_engine) -> Tuple[date, Dict[str, List[Dict[str, Any]]]]:
    """
    Validates the day pack against schema, dates, and live store integrity.
    Returns (pack_date, parsed_data_dict) on success.
    Raises PackValidationError on any failure.
    """
    if not pack_dir.exists() or not pack_dir.is_dir():
        raise PackValidationError(f"Pack directory does not exist: {pack_dir}")

    # Check required files
    for rf in REQUIRED_FILES:
        fp = pack_dir / rf
        if not fp.exists():
            raise PackValidationError(f"Missing required file '{rf}' in pack {pack_dir.name}")

    # Read metadata
    meta_path = pack_dir / "metadata.json"
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
    except Exception as exc:
        raise PackValidationError(f"Invalid metadata.json in pack: {exc}")

    pack_date_str = meta.get("pack_date")
    if not pack_date_str:
        raise PackValidationError("metadata.json missing 'pack_date'")
    try:
        pack_date = datetime.strptime(pack_date_str, "%Y-%m-%d").date()
    except Exception:
        raise PackValidationError(f"Invalid pack_date format: {pack_date_str}")

    # Enforce strict date continuity: exactly the day after current_day
    from stage9.current_day import get_current_day
    cur_day = get_current_day()
    expected_day = cur_day + timedelta(days=1)
    if pack_date != expected_day:
        raise PackValidationError(
            f"Date violation: date continuity error: this pack is for {pack_date.day} {pack_date.strftime('%b %Y')} "
            f"but the current day is {cur_day.day} {cur_day.strftime('%b %Y')}, "
            f"so {expected_day.day} {expected_day.strftime('%b %Y')} was expected."
        )

    parsed_data: Dict[str, List[Dict[str, Any]]] = {}

    with live_engine.connect() as conn:
        for tbl, expected_cols in EXPECTED_COLUMNS.items():
            csv_path = pack_dir / f"{tbl}.csv"
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                actual_cols = reader.fieldnames or []
                if list(actual_cols) != expected_cols:
                    raise PackValidationError(
                        f"Column mismatch in {tbl}.csv. Expected: {expected_cols}, Got: {actual_cols}"
                    )
                rows = list(reader)

            # Date checks and type conversions
            date_col = DATE_COLUMNS.get(tbl)
            for i, row in enumerate(rows):
                if date_col and row.get(date_col):
                    row_d = row[date_col].strip()
                    if row_d != pack_date_str:
                        raise PackValidationError(
                            f"Date violation in {tbl}.csv row {i+1}: expected date '{pack_date_str}', found '{row_d}'"
                        )

                # Primary key check for duplicates in live DB
                pk_val = row.get("id")
                if pk_val:
                    exists = conn.execute(
                        text(f"SELECT 1 FROM {tbl} WHERE id = :id LIMIT 1"),
                        {"id": int(pk_val)}
                    ).scalar()
                    if exists:
                        raise PackValidationError(
                            f"Duplicate primary key {pk_val} in {tbl}.csv already exists in live database"
                        )

            parsed_data[tbl] = rows

    return pack_date, parsed_data


def ingest_pack(pack_dir: Path) -> Dict[str, Any]:
    """
    Validates and ingests a single day pack into live/sage_live.db.
    """
    if not LIVE_DB_PATH.exists():
        from stage9.init_live_db import init_live_db
        init_live_db()

    live_engine = create_engine(f"sqlite:///{LIVE_DB_PATH}")

    pack_date, parsed_data = validate_pack(pack_dir, live_engine)
    pack_date_str = pack_date.isoformat()

    # Perform atomic load
    total_inserted = 0
    with live_engine.begin() as conn:
        for tbl, rows in parsed_data.items():
            if not rows:
                continue
            cols = EXPECTED_COLUMNS[tbl]
            placeholders = ", ".join([f":{c}" for c in cols])
            ins_sql = text(f"INSERT INTO {tbl} ({', '.join(cols)}) VALUES ({placeholders})")

            # Clean rows: empty strings to None for nullable integer/date columns
            cleaned_rows = []
            for r in rows:
                clean_r = {}
                for k, v in r.items():
                    if v == "":
                        clean_r[k] = None
                    elif k in ("id", "po_id", "supplier_id", "material_id", "quantity_ordered",
                              "quantity_received", "customer_id", "sales_order_id", "product_id",
                              "quantity_fulfilled", "sales_order_line_id", "delivery_id",
                              "quantity_shipped", "planned_qty", "actual_qty", "production_order_id",
                              "item_id", "planned_quantity", "quantity_issued", "goods_receipt_line_id",
                              "material_issue_id", "delivery_line_id"):
                        clean_r[k] = int(v) if v is not None else None
                    else:
                        clean_r[k] = v
                cleaned_rows.append(clean_r)

            conn.execute(ins_sql, cleaned_rows)
            total_inserted += len(cleaned_rows)

        # Update purchase_order_lines quantity_received if goods receipts were ingested
        if parsed_data.get("goods_receipt_lines"):
            for grl in parsed_data["goods_receipt_lines"]:
                po_line_id = int(grl["po_line_id"])
                rec_qty = int(grl["quantity_received"])
                conn.execute(
                    text("UPDATE purchase_order_lines SET quantity_received = COALESCE(quantity_received, 0) + :qty WHERE id = :id"),
                    {"qty": rec_qty, "id": po_line_id}
                )
            # Recompute PO statuses
            conn.execute(text("""
                UPDATE purchase_orders
                SET status = CASE
                    WHEN (SELECT SUM(quantity_received) FROM purchase_order_lines WHERE po_id = purchase_orders.id) >=
                         (SELECT SUM(quantity_ordered) FROM purchase_order_lines WHERE po_id = purchase_orders.id)
                    THEN 'Complete'
                    WHEN (SELECT SUM(quantity_received) FROM purchase_order_lines WHERE po_id = purchase_orders.id) > 0
                    THEN 'Partial'
                    ELSE status
                END
                WHERE id IN (SELECT DISTINCT po_id FROM goods_receipts WHERE receipt_date = :d)
            """), {"d": pack_date_str})

        # Update sales_order_lines quantity_fulfilled if deliveries were ingested
        if parsed_data.get("delivery_lines"):
            for dl in parsed_data["delivery_lines"]:
                sol_id = int(dl["sales_order_line_id"])
                shp_qty = int(dl["quantity_shipped"])
                conn.execute(
                    text("UPDATE sales_order_lines SET quantity_fulfilled = COALESCE(quantity_fulfilled, 0) + :qty WHERE id = :id"),
                    {"qty": shp_qty, "id": sol_id}
                )
            # Recompute SO statuses
            conn.execute(text("""
                UPDATE sales_orders
                SET status = CASE
                    WHEN (SELECT SUM(quantity_fulfilled) FROM sales_order_lines WHERE sales_order_id = sales_orders.id) >=
                         (SELECT SUM(quantity_ordered) FROM sales_order_lines WHERE sales_order_id = sales_orders.id)
                    THEN 'Complete'
                    WHEN (SELECT SUM(quantity_fulfilled) FROM sales_order_lines WHERE sales_order_id = sales_orders.id) > 0
                    THEN 'Partial'
                    ELSE status
                END
                WHERE id IN (SELECT DISTINCT sales_order_id FROM deliveries WHERE ship_date = :d)
            """), {"d": pack_date_str})

    # Update global current_day and clock
    register_ingested_day(pack_date)
    set_replay_date(pack_date)

    # Update daily_panel_live.parquet
    EXT_PANEL_PATH = ROOT_DIR / "analytics" / "daily_panel_ext.parquet"
    if EXT_PANEL_PATH.exists() and LIVE_PANEL_PATH.exists():
        try:
            ext_df = pd.read_parquet(EXT_PANEL_PATH)
            live_df = pd.read_parquet(LIVE_PANEL_PATH)
            matching_row = ext_df[ext_df["date"] == pack_date_str]
            if not matching_row.empty:
                live_df = live_df[live_df["date"] != pack_date_str]
                updated_live_df = pd.concat([live_df, matching_row], ignore_index=True)
                updated_live_df.to_parquet(LIVE_PANEL_PATH, index=False)
        except Exception as exc:
            print(f"Warning updating live panel: {exc}")

    # Invalidate insights cache
    if INSIGHTS_CACHE_DIR.exists():
        for f in INSIGHTS_CACHE_DIR.glob("insights_*.json"):
            try:
                f.unlink()
            except Exception:
                pass

    # Append to ingest log
    INGEST_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pack_name": pack_dir.name,
        "pack_date": pack_date_str,
        "rows_ingested": total_inserted,
        "status": "SUCCESS"
    }
    with open(INGEST_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry) + "\n")

    return log_entry


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest operational day pack.")
    parser.add_argument("--pack", required=True, help="Path to day pack directory")
    args = parser.parse_args()

    pack_path = Path(args.pack)
    try:
        res = ingest_pack(pack_path)
        print(f"Successfully ingested pack '{pack_path.name}': {res['rows_ingested']} rows inserted. Current day: {res['pack_date']}")
    except PackValidationError as err:
        print(f"Pack validation failed: {err}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"Ingestion error: {exc}", file=sys.stderr)
        sys.exit(1)
