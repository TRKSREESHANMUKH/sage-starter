"""
stage10/forecast/data.py — Dataset builder for SAGE Next-Day Outlook.

Zero look-ahead guarantee:
For any day t, features contain ONLY values known on or before day t.
Targets represent values realized on day t+1.
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
BASELINE_PANEL_PATH = ROOT_DIR / "analytics" / "daily_panel_baseline.parquet"


def build_feature_dataset(
    start_date: date = date(2025, 1, 1),
    end_date: date = date(2025, 12, 31),
    source: str = "main",
    db_session=None
) -> pd.DataFrame:
    """
    Constructs the feature matrix and targets for each day t in [start_date, end_date].
    Features strictly represent knowledge at day t (end-of-day).
    Targets:
      - T1_target: New sales ordered on day t+1
      - T2_target: Units due on day t+1
    """
    # 1. Load baseline panel for material stocks and backlog
    df_panel = pd.read_parquet(BASELINE_PANEL_PATH)
    df_panel["date"] = pd.to_datetime(df_panel["date"]).dt.date
    df_panel = df_panel.set_index("date")

    # 2. Load Sales Orders from database
    close_sess = False
    if db_session is None:
        from app.database import SessionLocal
        db_session = SessionLocal(source=source)
        close_sess = True

    try:
        from app.models.sales import SalesOrder, SalesOrderLine
        so_records = (
            db_session.query(
                SalesOrder.id.label("so_id"),
                SalesOrder.order_date,
                SalesOrder.requested_delivery_date,
                SalesOrderLine.product_id,
                SalesOrderLine.quantity_ordered
            )
            .join(SalesOrderLine, SalesOrderLine.sales_order_id == SalesOrder.id)
            .all()
        )
        df_so = pd.DataFrame(so_records)
    finally:
        if close_sess:
            db_session.close()

    # Pre-index sales by order_date and requested_delivery_date
    sales_by_order_date = df_so.groupby("order_date")["quantity_ordered"].sum().to_dict()

    # Generate complete date sequence
    all_dates = []
    curr = start_date
    while curr <= end_date:
        all_dates.append(curr)
        curr += timedelta(days=1)

    # Pre-compute daily series for T1 and T2
    t1_series = {d: float(sales_by_order_date.get(d, 0.0)) for d in all_dates}
    # Add buffer days before start_date if available
    buf_dates = [start_date - timedelta(days=i) for i in range(14, 0, -1)]
    for d in buf_dates:
        t1_series[d] = float(sales_by_order_date.get(d, 0.0))

    rows = []
    for t in all_dates:
        t_next = t + timedelta(days=1)

        # Targets for tomorrow (t+1)
        # T1 target: sales ordered on t_next
        t1_target = float(sales_by_order_date.get(t_next, 0.0))

        # T2 target: units due on t_next from orders placed on or before t
        due_tomorrow_on_books = float(
            df_so[
                (df_so["requested_delivery_date"] == t_next) &
                (df_so["order_date"] <= t)
            ]["quantity_ordered"].sum()
        )
        t2_target = due_tomorrow_on_books

        # Features at day t (zero lookahead)
        dt = pd.to_datetime(t)
        weekday = dt.weekday()
        day_of_month = dt.day
        month = dt.month

        # Day-of-week one-hot
        dow_feats = {f"dow_{i}": 1.0 if weekday == i else 0.0 for i in range(7)}

        # T1 Lags & Rolling statistics ending at t
        lag_1 = t1_series.get(t, 0.0)
        lag_2 = t1_series.get(t - timedelta(days=1), 0.0)
        lag_7 = t1_series.get(t - timedelta(days=6), 0.0)
        trailing_7 = [t1_series.get(t - timedelta(days=k), 0.0) for k in range(7)]
        rolling_7_mean = float(np.mean(trailing_7))
        rolling_7_std = float(np.std(trailing_7))

        # T2 Lags & Rolling statistics ending at t
        # Units due on day t ordered <= t-1
        due_t = float(
            df_so[
                (df_so["requested_delivery_date"] == t) &
                (df_so["order_date"] <= t - timedelta(days=1))
            ]["quantity_ordered"].sum()
        )
        due_lag_1 = due_t
        due_lag_2 = float(
            df_so[
                (df_so["requested_delivery_date"] == t - timedelta(days=1)) &
                (df_so["order_date"] <= t - timedelta(days=2))
            ]["quantity_ordered"].sum()
        )
        due_lag_7 = float(
            df_so[
                (df_so["requested_delivery_date"] == t - timedelta(days=6)) &
                (df_so["order_date"] <= t - timedelta(days=7))
            ]["quantity_ordered"].sum()
        )

        # Operational state from panel at day t
        if t in df_panel.index:
            p_row = df_panel.loc[t]
            mat_101 = float(p_row.get("material_101_stock", 0.0))
            mat_102 = float(p_row.get("material_102_stock", 0.0))
            mat_103 = float(p_row.get("material_103_stock", 0.0))
            bklg_201 = float(p_row.get("product_201_due_backlog_units", 0.0))
            bklg_202 = float(p_row.get("product_202_due_backlog_units", 0.0))
            open_backlog = bklg_201 + bklg_202
            fg_stock = float(p_row.get("product_201_fg_stock", 0.0)) + float(p_row.get("product_202_fg_stock", 0.0))
            planned_prod_next = (
                float(df_panel.loc[t_next].get("product_201_planned_production", 0.0)) +
                float(df_panel.loc[t_next].get("product_202_planned_production", 0.0))
                if t_next in df_panel.index else 50.0
            )
        else:
            mat_101, mat_102, mat_103 = 100.0, 100.0, 100.0
            open_backlog = 0.0
            fg_stock = 30.0
            planned_prod_next = 50.0

        row = {
            "date": t,
            "next_date": t_next,
            "day_of_month": float(day_of_month),
            "month": float(month),
            "weekday": weekday,
            **dow_feats,
            # T1 Features
            "t1_lag_1": lag_1,
            "t1_lag_2": lag_2,
            "t1_lag_7": lag_7,
            "t1_rolling_7_mean": rolling_7_mean,
            "t1_rolling_7_std": rolling_7_std,
            # T2 Features
            "t2_lag_1": due_lag_1,
            "t2_lag_2": due_lag_2,
            "t2_lag_7": due_lag_7,
            "units_due_tomorrow_on_books": due_tomorrow_on_books,
            # Operational Context
            "open_customer_backlog": open_backlog,
            "material_101_stock": mat_101,
            "material_102_stock": mat_102,
            "material_103_stock": mat_103,
            "fg_stock": fg_stock,
            "planned_prod_next": planned_prod_next,
            # Ground-truth targets on t+1
            "T1_target": t1_target,
            "T2_target": t2_target,
        }
        rows.append(row)

    df_out = pd.DataFrame(rows)
    return df_out


if __name__ == "__main__":
    df = build_feature_dataset()
    print("Feature dataset built successfully:")
    print("Shape:", df.shape)
    print("Columns:", df.columns.tolist())
    print(df.head(3))
