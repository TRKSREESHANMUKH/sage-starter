"""
stage10/forecast/data.py — Dataset builder for SAGE Weekly Order Forward-Look.

Protocol (Pre-registered in stage10/prereg_forecast_v3.md):
- Origin day D:
  - Target 1: Total NEW order units placed in D+1..D+7 (per product 201, 202, and total)
  - Target 2: Known order units already placed on or before D with requested_delivery_date in D+1..D+7
- Zero look-ahead: Features at D contain ONLY data on or before D.
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


def load_raw_sales_orders(db_session=None, source: str = "main") -> pd.DataFrame:
    """Loads all sales orders with order_date, requested_delivery_date, product_id, and quantity."""
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
                SalesOrder.status,
                SalesOrderLine.product_id,
                SalesOrderLine.quantity_ordered
            )
            .join(SalesOrderLine, SalesOrderLine.sales_order_id == SalesOrder.id)
            .filter(SalesOrder.status != "Cancelled")
            .all()
        )
        df_so = pd.DataFrame([
            {
                "so_id": r.so_id,
                "order_date": r.order_date,
                "requested_delivery_date": r.requested_delivery_date,
                "status": r.status,
                "product_id": r.product_id,
                "quantity_ordered": r.quantity_ordered
            }
            for r in so_records
        ])
    finally:
        if close_sess:
            db_session.close()

    return df_so


def get_known_due_orders(
    df_so: pd.DataFrame,
    origin_d: date,
    horizon_days: int = 7,
    product_id: Optional[int] = None
) -> int:
    """
    Computes exact units already on the books at origin_d that are due in [origin_d+1, origin_d+horizon_days].
    Zero look-ahead: order_date <= origin_d.
    """
    if df_so.empty:
        return 0
    d_start = origin_d + timedelta(days=1)
    d_end = origin_d + timedelta(days=horizon_days)

    mask = (
        (df_so["order_date"] <= origin_d) &
        (df_so["requested_delivery_date"] >= d_start) &
        (df_so["requested_delivery_date"] <= d_end)
    )
    if product_id is not None:
        mask = mask & (df_so["product_id"] == product_id)

    return int(df_so.loc[mask, "quantity_ordered"].sum())


def build_daily_demand_series(
    df_so: pd.DataFrame,
    start_date: date = date(2024, 11, 1),
    end_date: date = date(2026, 1, 15)
) -> pd.DataFrame:
    """Builds continuous daily time series of demand units for 201, 202, and Total."""
    dates = pd.date_range(start_date, end_date)
    daily = pd.DataFrame({"date": [d.date() for d in dates]})

    for pid in [201, 202]:
        p_so = df_so[df_so["product_id"] == pid].groupby("order_date")["quantity_ordered"].sum().to_dict()
        daily[f"dem_{pid}"] = daily["date"].map(lambda d: p_so.get(d, 0))

    daily["dem_total"] = daily["dem_201"] + daily["dem_202"]
    return daily


def build_weekly_forecast_dataset(
    start_origin: date = date(2025, 1, 1),
    end_origin: date = date(2025, 12, 24),
    source: str = "main",
    db_session=None
) -> pd.DataFrame:
    """
    Constructs origin-level dataset where for each origin date D:
    Features: calendar features at D, demand lags (1, 7, 14, 28), rolling sums/means (7, 14, 28).
    Targets: Total new order units placed on [D+1..D+7] for 201, 202, and Total.
    Known facts: Units due in [D+1..D+7] known at D.
    """
    df_so = load_raw_sales_orders(db_session=db_session, source=source)
    daily = build_daily_demand_series(df_so, start_date=start_origin - timedelta(days=35), end_date=end_origin + timedelta(days=10))
    daily_map = daily.set_index("date").to_dict(orient="index")

    rows = []
    curr = start_origin
    while curr <= end_origin:
        dt = pd.to_datetime(curr)
        weekday = curr.weekday()
        month = curr.month
        week_of_year = dt.isocalendar()[1]

        # Targets for next 7 days
        tgt_201 = sum(daily_map.get(curr + timedelta(days=k), {}).get("dem_201", 0) for k in range(1, 8))
        tgt_202 = sum(daily_map.get(curr + timedelta(days=k), {}).get("dem_202", 0) for k in range(1, 8))
        tgt_total = tgt_201 + tgt_202

        # Known due orders
        due_201 = get_known_due_orders(df_so, curr, horizon_days=7, product_id=201)
        due_202 = get_known_due_orders(df_so, curr, horizon_days=7, product_id=202)
        due_total = due_201 + due_202

        # Features per product and total
        row = {
            "origin_date": curr,
            "weekday": weekday,
            "month": month,
            "week_of_year": week_of_year,
            "target_total": tgt_total,
            "target_201": tgt_201,
            "target_202": tgt_202,
            "due_total": due_total,
            "due_201": due_201,
            "due_202": due_202,
        }

        for target_key, col in [("total", "dem_total"), ("201", "dem_201"), ("202", "dem_202")]:
            row[f"{target_key}_trailing_7"] = sum(daily_map.get(curr - timedelta(days=k), {}).get(col, 0) for k in range(7))
            row[f"{target_key}_trailing_14"] = sum(daily_map.get(curr - timedelta(days=k), {}).get(col, 0) for k in range(14))
            row[f"{target_key}_trailing_28"] = sum(daily_map.get(curr - timedelta(days=k), {}).get(col, 0) for k in range(28))
            row[f"{target_key}_lag_0"] = daily_map.get(curr, {}).get(col, 0)
            row[f"{target_key}_lag_1"] = daily_map.get(curr - timedelta(days=1), {}).get(col, 0)
            row[f"{target_key}_lag_7"] = daily_map.get(curr - timedelta(days=7), {}).get(col, 0)
            row[f"{target_key}_lag_14"] = daily_map.get(curr - timedelta(days=14), {}).get(col, 0)
            row[f"{target_key}_lag_28"] = daily_map.get(curr - timedelta(days=28), {}).get(col, 0)

        rows.append(row)
        curr += timedelta(days=1)

    return pd.DataFrame(rows)


if __name__ == "__main__":
    df = build_weekly_forecast_dataset()
    print(f"Weekly forecast dataset generated: {df.shape[0]} origins, {df.shape[1]} columns.")
    print("Sample origin 2025-06-01:")
    print(df[df['origin_date'] == date(2025, 6, 1)][['origin_date', 'target_total', 'due_total', 'total_trailing_7', 'total_trailing_28']])
