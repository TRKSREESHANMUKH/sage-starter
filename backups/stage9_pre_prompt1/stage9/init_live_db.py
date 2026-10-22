"""
stage9/init_live_db.py — Initializes the live SQLite operational store.

Part 2 Requirement:
- live/sage_live.db (SQLite) stores the 16 operational tables.
- Initialized with all rows dated on or before 2025-02-02 (the day before the demo week).
- Never writes to the main PostgreSQL database.
- Saves live/sage_live_baseline.db for instant reset.
"""

from __future__ import annotations

import os
import shutil
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
LIVE_DIR = ROOT_DIR / "live"
LIVE_DB_PATH = LIVE_DIR / "sage_live.db"
LIVE_BASELINE_PATH = LIVE_DIR / "sage_live_baseline.db"

from app.database import Base
from app.models import suppliers, purchasing, inventory, production, sales

CUTOFF_DATE = date(2025, 12, 31)


def init_live_db(cutoff: date = CUTOFF_DATE) -> Path:
    """
    Initializes live/sage_live.db from PostgreSQL up to cutoff date.
    """
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL required to initialize live database.")

    LIVE_DIR.mkdir(parents=True, exist_ok=True)
    if LIVE_DB_PATH.exists():
        LIVE_DB_PATH.unlink()

    pg_engine = create_engine(DATABASE_URL)
    sqlite_engine = create_engine(f"sqlite:///{LIVE_DB_PATH}")

    # 1. Create table schemas
    Base.metadata.create_all(bind=sqlite_engine)

    with pg_engine.connect() as pg_conn, sqlite_engine.begin() as sqlite_conn:
        # Master data
        for tbl in ["suppliers", "customers", "products", "inventory_items", "bill_of_materials"]:
            rows = pg_conn.execute(text(f"SELECT * FROM {tbl}")).mappings().fetchall()
            if rows:
                cols = list(rows[0].keys())
                placeholders = ", ".join([f":{c}" for c in cols])
                col_names = ", ".join(cols)
                ins_sql = text(f"INSERT INTO {tbl} ({col_names}) VALUES ({placeholders})")
                sqlite_conn.execute(ins_sql, [dict(r) for r in rows])
                print(f"Loaded master table {tbl}: {len(rows)} rows")

        # Operational tables with date <= cutoff
        # Goods Receipts & Lines
        gr_rows = pg_conn.execute(
            text("SELECT * FROM goods_receipts WHERE receipt_date <= :d ORDER BY id"),
            {"d": cutoff}
        ).mappings().fetchall()
        if gr_rows:
            cols = list(gr_rows[0].keys())
            ins_sql = text(f"INSERT INTO goods_receipts ({', '.join(cols)}) VALUES ({', '.join([':'+c for c in cols])})")
            sqlite_conn.execute(ins_sql, [dict(r) for r in gr_rows])
            gr_ids = [g["id"] for g in gr_rows]
            grl_rows = pg_conn.execute(
                text("SELECT * FROM goods_receipt_lines WHERE receipt_id = ANY(:ids) ORDER BY id"),
                {"ids": gr_ids}
            ).mappings().fetchall()
            if grl_rows:
                cols_grl = list(grl_rows[0].keys())
                ins_sql_grl = text(f"INSERT INTO goods_receipt_lines ({', '.join(cols_grl)}) VALUES ({', '.join([':'+c for c in cols_grl])})")
                sqlite_conn.execute(ins_sql_grl, [dict(r) for r in grl_rows])
        print(f"Loaded goods_receipts: {len(gr_rows)} rows")

        # Purchase Orders & Lines
        po_rows = pg_conn.execute(
            text("SELECT * FROM purchase_orders WHERE order_date <= :d ORDER BY id"),
            {"d": cutoff}
        ).mappings().fetchall()
        if po_rows:
            # Recompute PO status and quantity_received as of cutoff
            po_dicts = []
            for po in po_rows:
                d = dict(po)
                po_dicts.append(d)
            cols = list(po_dicts[0].keys())
            ins_sql = text(f"INSERT INTO purchase_orders ({', '.join(cols)}) VALUES ({', '.join([':'+c for c in cols])})")
            sqlite_conn.execute(ins_sql, po_dicts)

            po_ids = [p["id"] for p in po_rows]
            pol_rows = pg_conn.execute(
                text("SELECT * FROM purchase_order_lines WHERE po_id = ANY(:ids) ORDER BY id"),
                {"ids": po_ids}
            ).mappings().fetchall()
            pol_dicts = []
            for pol in pol_rows:
                d = dict(pol)
                # Compute received up to cutoff
                rec_sum = pg_conn.execute(
                    text("""
                        SELECT COALESCE(SUM(grl.quantity_received), 0)
                        FROM goods_receipts gr
                        JOIN goods_receipt_lines grl ON gr.id = grl.receipt_id
                        WHERE gr.po_id = :po_id AND grl.po_line_id = :pol_id AND gr.receipt_date <= :d
                    """),
                    {"po_id": d["po_id"], "pol_id": d["id"], "d": cutoff}
                ).scalar() or 0
                d["quantity_received"] = rec_sum
                pol_dicts.append(d)
            if pol_dicts:
                cols_pol = list(pol_dicts[0].keys())
                ins_sql_pol = text(f"INSERT INTO purchase_order_lines ({', '.join(cols_pol)}) VALUES ({', '.join([':'+c for c in cols_pol])})")
                sqlite_conn.execute(ins_sql_pol, pol_dicts)
        print(f"Loaded purchase_orders: {len(po_rows)} rows")

        # Deliveries & Lines
        del_rows = pg_conn.execute(
            text("SELECT * FROM deliveries WHERE ship_date <= :d ORDER BY id"),
            {"d": cutoff}
        ).mappings().fetchall()
        if del_rows:
            cols = list(del_rows[0].keys())
            ins_sql = text(f"INSERT INTO deliveries ({', '.join(cols)}) VALUES ({', '.join([':'+c for c in cols])})")
            sqlite_conn.execute(ins_sql, [dict(r) for r in del_rows])
            del_ids = [dl["id"] for dl in del_rows]
            dl_rows = pg_conn.execute(
                text("SELECT * FROM delivery_lines WHERE delivery_id = ANY(:ids) ORDER BY id"),
                {"ids": del_ids}
            ).mappings().fetchall()
            if dl_rows:
                cols_dl = list(dl_rows[0].keys())
                ins_sql_dl = text(f"INSERT INTO delivery_lines ({', '.join(cols_dl)}) VALUES ({', '.join([':'+c for c in cols_dl])})")
                sqlite_conn.execute(ins_sql_dl, [dict(r) for r in dl_rows])
        print(f"Loaded deliveries: {len(del_rows)} rows")

        # Sales Orders & Lines
        so_rows = pg_conn.execute(
            text("SELECT * FROM sales_orders WHERE order_date <= :d ORDER BY id"),
            {"d": cutoff}
        ).mappings().fetchall()
        if so_rows:
            so_dicts = [dict(s) for s in so_rows]
            cols = list(so_dicts[0].keys())
            ins_sql = text(f"INSERT INTO sales_orders ({', '.join(cols)}) VALUES ({', '.join([':'+c for c in cols])})")
            sqlite_conn.execute(ins_sql, so_dicts)

            so_ids = [s["id"] for s in so_rows]
            sol_rows = pg_conn.execute(
                text("SELECT * FROM sales_order_lines WHERE sales_order_id = ANY(:ids) ORDER BY id"),
                {"ids": so_ids}
            ).mappings().fetchall()
            sol_dicts = []
            for sol in sol_rows:
                d = dict(sol)
                # Compute fulfilled up to cutoff
                ful_sum = pg_conn.execute(
                    text("""
                        SELECT COALESCE(SUM(dl.quantity_shipped), 0)
                        FROM deliveries del
                        JOIN delivery_lines dl ON del.id = dl.delivery_id
                        WHERE del.sales_order_id = :so_id AND dl.sales_order_line_id = :sol_id AND del.ship_date <= :d
                    """),
                    {"so_id": d["sales_order_id"], "sol_id": d["id"], "d": cutoff}
                ).scalar() or 0
                d["quantity_fulfilled"] = ful_sum
                sol_dicts.append(d)
            if sol_dicts:
                cols_sol = list(sol_dicts[0].keys())
                ins_sql_sol = text(f"INSERT INTO sales_order_lines ({', '.join(cols_sol)}) VALUES ({', '.join([':'+c for c in cols_sol])})")
                sqlite_conn.execute(ins_sql_sol, sol_dicts)
        print(f"Loaded sales_orders: {len(so_rows)} rows")

        # Production Orders
        po_prod_rows = pg_conn.execute(
            text("SELECT * FROM production_orders WHERE planned_start <= :d ORDER BY id"),
            {"d": cutoff}
        ).mappings().fetchall()
        if po_prod_rows:
            cols = list(po_prod_rows[0].keys())
            ins_sql = text(f"INSERT INTO production_orders ({', '.join(cols)}) VALUES ({', '.join([':'+c for c in cols])})")
            sqlite_conn.execute(ins_sql, [dict(r) for r in po_prod_rows])
        print(f"Loaded production_orders: {len(po_prod_rows)} rows")

        # Material Issues
        mi_rows = pg_conn.execute(
            text("SELECT * FROM material_issues WHERE planned_issue_date <= :d ORDER BY id"),
            {"d": cutoff}
        ).mappings().fetchall()
        if mi_rows:
            cols = list(mi_rows[0].keys())
            ins_sql = text(f"INSERT INTO material_issues ({', '.join(cols)}) VALUES ({', '.join([':'+c for c in cols])})")
            sqlite_conn.execute(ins_sql, [dict(r) for r in mi_rows])
        print(f"Loaded material_issues: {len(mi_rows)} rows")

        # Stock Movements
        sm_rows = pg_conn.execute(
            text("SELECT * FROM stock_movements WHERE date <= :d ORDER BY id"),
            {"d": cutoff}
        ).mappings().fetchall()
        if sm_rows:
            cols = list(sm_rows[0].keys())
            ins_sql = text(f"INSERT INTO stock_movements ({', '.join(cols)}) VALUES ({', '.join([':'+c for c in cols])})")
            sqlite_conn.execute(ins_sql, [dict(r) for r in sm_rows])
        print(f"Loaded stock_movements: {len(sm_rows)} rows")

    # Save copy as baseline
    shutil.copy2(LIVE_DB_PATH, LIVE_BASELINE_PATH)
    print(f"Live database successfully initialized at {LIVE_DB_PATH} (baseline saved).")
    return LIVE_DB_PATH


if __name__ == "__main__":
    init_live_db()
