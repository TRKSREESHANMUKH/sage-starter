"""
stage10/forecast/evaluate_demo.py — Evaluate frozen production forecast model on 10 demo days (2026-01-01 to 2026-01-10).
"""

from __future__ import annotations

import json
import pickle
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List
import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from stage10.forecast.models import compute_metrics, FEATURE_COLS_T1, FEATURE_COLS_T2

MODEL_PKL_PATH = ROOT_DIR / "stage10" / "forecast" / "model.pkl"
METRICS_JSON_PATH = ROOT_DIR / "stage10" / "forecast" / "metrics.json"
DEMO_EVAL_JSON_PATH = ROOT_DIR / "stage10" / "forecast" / "demo_eval.json"
DEMO_PACKS_DIR = ROOT_DIR / "demo_data" / "packs"


def load_demo_orders() -> pd.DataFrame:
    records = []
    for d_path in sorted(DEMO_PACKS_DIR.glob("2026-01-*")):
        so_file = d_path / "sales_orders.csv"
        sol_file = d_path / "sales_order_lines.csv"
        if so_file.exists() and sol_file.exists():
            df_so = pd.read_csv(so_file)
            df_sol = pd.read_csv(sol_file)
            merged = pd.merge(df_so, df_sol, left_on="id", right_on="sales_order_id")
            for _, r in merged.iterrows():
                records.append({
                    "order_date": date.fromisoformat(str(r["order_date"])),
                    "requested_delivery_date": date.fromisoformat(str(r["requested_delivery_date"])),
                    "product_id": int(r["product_id"]),
                    "quantity_ordered": float(r["quantity_ordered"])
                })
    return pd.DataFrame(records)


def evaluate_demo_days() -> Dict[str, Any]:
    print("Loading frozen forecast model artifact...")
    with open(MODEL_PKL_PATH, "rb") as f:
        artifact = pickle.load(f)

    est_p50_t1 = artifact["t1_p50"]
    est_p10_t1 = artifact["t1_p10"]
    est_p90_t1 = artifact["t1_p90"]

    est_p50_t2 = artifact["t2_p50"]
    est_p10_t2 = artifact["t2_p10"]
    est_p90_t2 = artifact["t2_p90"]

    df_demo_so = load_demo_orders()
    sales_by_order_date = df_demo_so.groupby("order_date")["quantity_ordered"].sum().to_dict()

    # Baseline 2025 trailing data for the first few demo days (lags into Dec 2025)
    from stage10.forecast.data import build_feature_dataset
    df_2025 = build_feature_dataset(start_date=date(2025, 12, 1), end_date=date(2025, 12, 31))
    df_2025_idx = df_2025.set_index("date")

    demo_dates = [date(2026, 1, d) for d in range(1, 11)]

    # Inventory and backlog ground truth per demo day
    # Derived from snapshots or packs
    from stage9.snapshot import compute_daily_snapshot
    demo_snapshots = {}
    for d in demo_dates:
        snap_file = ROOT_DIR / "analytics" / "snapshots" / f"snapshot_{d.isoformat()}.json"
        if snap_file.exists():
            with open(snap_file, "r", encoding="utf-8") as f:
                demo_snapshots[d] = json.load(f)
        else:
            try:
                demo_snapshots[d] = compute_daily_snapshot(d, source="live")
            except Exception:
                demo_snapshots[d] = {}

    rows = []
    daily_records = []

    for d in demo_dates:
        d_next = d + timedelta(days=1)
        dt = pd.to_datetime(d)
        weekday = dt.weekday()
        day_of_month = dt.day
        month = dt.month

        dow_feats = {f"dow_{i}": 1.0 if weekday == i else 0.0 for i in range(7)}

        # T1 Lags
        def get_t1(d_eval):
            if d_eval in sales_by_order_date:
                return sales_by_order_date[d_eval]
            if d_eval in df_2025_idx.index:
                return float(df_2025_idx.loc[d_eval]["t1_lag_1"])
            return 0.0

        lag_1 = get_t1(d)
        lag_2 = get_t1(d - timedelta(days=1))
        lag_7 = get_t1(d - timedelta(days=6))
        trailing_7 = [get_t1(d - timedelta(days=k)) for k in range(7)]
        rolling_7_mean = float(np.mean(trailing_7))
        rolling_7_std = float(np.std(trailing_7))

        # T2 Lags & Book
        due_tomorrow_on_books = float(
            df_demo_so[
                (df_demo_so["requested_delivery_date"] == d_next) &
                (df_demo_so["order_date"] <= d)
            ]["quantity_ordered"].sum()
        )

        snap = demo_snapshots.get(d, {})
        kpis = snap.get("kpis", {})
        mats = snap.get("materials", {})
        prods = snap.get("products", {})

        open_bklg = float(kpis.get("total_backlog_units", 0.0))
        mat_101 = float(mats.get("101", {}).get("stock", 100.0))
        mat_102 = float(mats.get("102", {}).get("stock", 100.0))
        mat_103 = float(mats.get("103", {}).get("stock", 100.0))
        fg_stock = sum(float(p.get("fg_stock", 15.0)) for p in prods.values()) or 30.0

        # Planned production next day
        plan_next = 50.0

        feat_row_t1 = {
            "dow_0": dow_feats["dow_0"], "dow_1": dow_feats["dow_1"], "dow_2": dow_feats["dow_2"],
            "dow_3": dow_feats["dow_3"], "dow_4": dow_feats["dow_4"], "dow_5": dow_feats["dow_5"],
            "dow_6": dow_feats["dow_6"],
            "day_of_month": float(day_of_month), "month": float(month),
            "t1_lag_1": lag_1, "t1_lag_2": lag_2, "t1_lag_7": lag_7,
            "t1_rolling_7_mean": rolling_7_mean, "t1_rolling_7_std": rolling_7_std,
            "open_customer_backlog": open_bklg,
            "units_due_tomorrow_on_books": due_tomorrow_on_books,
            "material_101_stock": mat_101, "material_102_stock": mat_102, "material_103_stock": mat_103
        }

        feat_row_t2 = {
            "dow_0": dow_feats["dow_0"], "dow_1": dow_feats["dow_1"], "dow_2": dow_feats["dow_2"],
            "dow_3": dow_feats["dow_3"], "dow_4": dow_feats["dow_4"], "dow_5": dow_feats["dow_5"],
            "dow_6": dow_feats["dow_6"],
            "day_of_month": float(day_of_month), "month": float(month),
            "t2_lag_1": float(df_demo_so[(df_demo_so["requested_delivery_date"] == d) & (df_demo_so["order_date"] <= d - timedelta(days=1))]["quantity_ordered"].sum()),
            "t2_lag_2": 0.0,
            "t2_lag_7": 0.0,
            "units_due_tomorrow_on_books": due_tomorrow_on_books,
            "open_customer_backlog": open_bklg,
            "material_101_stock": mat_101, "material_102_stock": mat_102, "material_103_stock": mat_103
        }

        X_t1 = np.array([[feat_row_t1[c] for c in FEATURE_COLS_T1]])
        X_t2 = np.array([[feat_row_t2[c] for c in FEATURE_COLS_T2]])

        pred_t1_p50 = float(max(0.0, est_p50_t1.predict(X_t1)[0]))
        pred_t1_p10 = float(max(0.0, est_p10_t1.predict(X_t1)[0]))
        pred_t1_p90 = float(max(pred_t1_p10, est_p90_t1.predict(X_t1)[0]))

        pred_t2_p50 = float(max(0.0, est_p50_t2.predict(X_t2)[0]))
        pred_t2_p10 = float(max(0.0, est_p10_t2.predict(X_t2)[0]))
        pred_t2_p90 = float(max(pred_t2_p10, est_p90_t2.predict(X_t2)[0]))

        # Ground truth values for day t+1
        actual_t1 = sales_by_order_date.get(d_next, None)
        actual_t2 = float(
            df_demo_so[
                df_demo_so["requested_delivery_date"] == d_next
            ]["quantity_ordered"].sum()
        ) if d <= date(2026, 1, 9) else None

        # Shortage risk
        buf_next = fg_stock + plan_next - due_tomorrow_on_books
        if buf_next < 0:
            shortage_risk = "HIGH"
        elif buf_next < 25.0:
            shortage_risk = "MEDIUM"
        else:
            shortage_risk = "LOW"

        record = {
            "date": d.isoformat(),
            "target_date": d_next.isoformat(),
            "t1_pred_p50": round(pred_t1_p50, 1),
            "t1_p10": round(pred_t1_p10, 1),
            "t1_p90": round(pred_t1_p90, 1),
            "t1_actual": float(actual_t1) if actual_t1 is not None else None,
            "t2_on_books": round(due_tomorrow_on_books, 1),
            "t2_pred_p50": round(pred_t2_p50, 1),
            "t2_p10": round(pred_t2_p10, 1),
            "t2_p90": round(pred_t2_p90, 1),
            "t2_actual": float(actual_t2) if actual_t2 is not None else None,
            "shortage_risk": shortage_risk,
            "projected_buffer": round(buf_next, 1)
        }
        daily_records.append(record)

    # Evaluate metrics on the 9 days where ground truth tomorrow is fully known (Days 1–9)
    eval_days = [r for r in daily_records if r["t1_actual"] is not None]
    y_t1_actual = np.array([r["t1_actual"] for r in eval_days])
    y_t1_pred = np.array([r["t1_pred_p50"] for r in eval_days])
    y_t1_p10 = np.array([r["t1_p10"] for r in eval_days])
    y_t1_p90 = np.array([r["t1_p90"] for r in eval_days])

    t1_demo_metrics = compute_metrics(y_t1_actual, y_t1_pred, y_t1_p10, y_t1_p90)

    # Compare to 2025 test metrics
    test_metrics = {}
    if METRICS_JSON_PATH.exists():
        with open(METRICS_JSON_PATH, "r", encoding="utf-8") as f:
            test_metrics = json.load(f)

    comparison = {
        "demo_period": "2026-01-01 to 2026-01-10 (10 demo days)",
        "demo_sample_size_evaluated_days": len(eval_days),
        "target_1_new_sales_demo_metrics": t1_demo_metrics,
        "test_period_2025_h2_metrics": test_metrics.get("target_1_new_sales", {}).get("model_d_gbdt", {}),
        "daily_forecasts": daily_records
    }

    with open(DEMO_EVAL_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(comparison, f, indent=2)

    print("Demo evaluation complete:")
    print(json.dumps(comparison["target_1_new_sales_demo_metrics"], indent=2))
    return comparison


if __name__ == "__main__":
    evaluate_demo_days()
