"""
stage10/forecast/models.py — Forecasting models and walk-forward evaluation protocol.

Models:
  (a) Naive lag-1
  (b) Same-weekday last week (lag-7)
  (c) 7-day rolling mean
  (d) HistGradientBoostingRegressor with quantile loss (p10, p50, p90)

Walk-Forward Protocol:
  - Train: 2025 Jan-Jun (first 181 days: 2025-01-01 to 2025-06-30)
  - Test: 2025 Jul-Dec (184 days: 2025-07-01 to 2025-12-31)
  - Evaluates WAPE, MAPE, MedAE, Bias, Coverage, RelImp
  - Evaluates Shortage Risk rule
  - Dumps metrics to stage10/forecast/metrics.json
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Tuple
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from stage10.forecast.data import build_feature_dataset

METRICS_JSON_PATH = ROOT_DIR / "stage10" / "forecast" / "metrics.json"

FEATURE_COLS_T1 = [
    "dow_0", "dow_1", "dow_2", "dow_3", "dow_4", "dow_5", "dow_6",
    "day_of_month", "month",
    "t1_lag_1", "t1_lag_2", "t1_lag_7",
    "t1_rolling_7_mean", "t1_rolling_7_std",
    "open_customer_backlog",
    "units_due_tomorrow_on_books",
    "material_101_stock", "material_102_stock", "material_103_stock"
]

FEATURE_COLS_T2 = [
    "dow_0", "dow_1", "dow_2", "dow_3", "dow_4", "dow_5", "dow_6",
    "day_of_month", "month",
    "t2_lag_1", "t2_lag_2", "t2_lag_7",
    "units_due_tomorrow_on_books",
    "open_customer_backlog",
    "material_101_stock", "material_102_stock", "material_103_stock"
]


def compute_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    p10: Optional[np.ndarray] = None,
    p90: Optional[np.ndarray] = None
) -> Dict[str, float]:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    sum_actual = float(np.sum(y_true))

    # WAPE
    wape = float(np.sum(np.abs(y_true - y_pred)) / sum_actual) if sum_actual > 0 else 0.0

    # MAPE on non-zero days
    nonzero_mask = y_true > 0
    if np.any(nonzero_mask):
        mape = float(np.mean(np.abs(y_true[nonzero_mask] - y_pred[nonzero_mask]) / y_true[nonzero_mask]) * 100.0)
    else:
        mape = 0.0

    # MedAE
    medae = float(np.median(np.abs(y_true - y_pred)))

    # Bias
    bias = float(np.mean(y_pred - y_true))

    # Coverage
    coverage = None
    if p10 is not None and p90 is not None:
        p10 = np.asarray(p10, dtype=float)
        p90 = np.asarray(p90, dtype=float)
        inside = (y_true >= p10) & (y_true <= p90)
        coverage = float(np.mean(inside) * 100.0)

    res = {
        "wape": round(wape, 4),
        "mape_pct": round(mape, 2),
        "medae": round(medae, 2),
        "bias": round(bias, 2),
    }
    if coverage is not None:
        res["coverage_pct"] = round(coverage, 2)
    return res


def run_walk_forward_evaluation(df: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
    if df is None:
        df = build_feature_dataset()

    split_date = date(2025, 6, 30)
    train_mask = df["date"] <= split_date
    test_mask = df["date"] > split_date

    df_train = df[train_mask].copy()
    df_test = df[test_mask].copy()

    print(f"Dataset split: Train = {len(df_train)} days, Test = {len(df_test)} days")

    # ──────────────────────────────────────────────────────────────────────────
    # TARGET 1: New Sales Tomorrow
    # ──────────────────────────────────────────────────────────────────────────
    y_test_t1 = df_test["T1_target"].values

    # Model (a): Naive lag-1
    pred_a_t1 = df_test["t1_lag_1"].values
    # Model (b): Same-weekday last week (lag-7)
    pred_b_t1 = df_test["t1_lag_7"].values
    # Model (c): 7-day rolling mean
    pred_c_t1 = df_test["t1_rolling_7_mean"].values

    # Model (d): HistGradientBoostingRegressor (p10, p50, p90)
    X_train_t1 = df_train[FEATURE_COLS_T1].values
    y_train_t1 = df_train["T1_target"].values

    est_p50_t1 = HistGradientBoostingRegressor(loss="quantile", quantile=0.50, random_state=42, max_iter=100)
    est_p10_t1 = HistGradientBoostingRegressor(loss="quantile", quantile=0.10, random_state=42, max_iter=100)
    est_p90_t1 = HistGradientBoostingRegressor(loss="quantile", quantile=0.90, random_state=42, max_iter=100)

    est_p50_t1.fit(X_train_t1, y_train_t1)
    est_p10_t1.fit(X_train_t1, y_train_t1)
    est_p90_t1.fit(X_train_t1, y_train_t1)

    X_test_t1 = df_test[FEATURE_COLS_T1].values
    pred_d_t1 = np.maximum(0.0, est_p50_t1.predict(X_test_t1))
    p10_d_t1 = np.maximum(0.0, est_p10_t1.predict(X_test_t1))
    p90_d_t1 = np.maximum(p10_d_t1, est_p90_t1.predict(X_test_t1))

    # Fallback (b) intervals using empirical residuals from train set
    train_res_b_t1 = y_train_t1 - df_train["t1_lag_7"].values
    res_p10_b = float(np.percentile(train_res_b_t1, 10))
    res_p90_b = float(np.percentile(train_res_b_t1, 90))
    p10_b_t1 = np.maximum(0.0, pred_b_t1 + res_p10_b)
    p90_b_t1 = np.maximum(p10_b_t1, pred_b_t1 + res_p90_b)

    metrics_t1 = {
        "model_a_naive": compute_metrics(y_test_t1, pred_a_t1),
        "model_b_weekday": compute_metrics(y_test_t1, pred_b_t1, p10_b_t1, p90_b_t1),
        "model_c_rolling7": compute_metrics(y_test_t1, pred_c_t1),
        "model_d_gbdt": compute_metrics(y_test_t1, pred_d_t1, p10_d_t1, p90_d_t1),
    }

    # Relative improvement of (d) over (b)
    wape_b = metrics_t1["model_b_weekday"]["wape"]
    wape_d = metrics_t1["model_d_gbdt"]["wape"]
    rel_imp_t1 = round(((wape_b - wape_d) / wape_b) * 100.0, 2) if wape_b > 0 else 0.0
    metrics_t1["model_d_gbdt"]["rel_improvement_vs_b_pct"] = rel_imp_t1

    cov_d_t1 = metrics_t1["model_d_gbdt"]["coverage_pct"]
    pass_t1 = (rel_imp_t1 >= 15.0) and (70.0 <= cov_d_t1 <= 90.0)
    metrics_t1["pre_registered_pass"] = bool(pass_t1)

    # ──────────────────────────────────────────────────────────────────────────
    # TARGET 2: Due Tomorrow
    # ──────────────────────────────────────────────────────────────────────────
    y_test_t2 = df_test["T2_target"].values

    pred_a_t2 = df_test["t2_lag_1"].values
    pred_b_t2 = df_test["t2_lag_7"].values
    pred_c_t2 = df_test["units_due_tomorrow_on_books"].rolling(7, min_periods=1).mean().values

    # Model (d): GBDT on T2
    X_train_t2 = df_train[FEATURE_COLS_T2].values
    y_train_t2 = df_train["T2_target"].values

    est_p50_t2 = HistGradientBoostingRegressor(loss="quantile", quantile=0.50, random_state=42, max_iter=100)
    est_p10_t2 = HistGradientBoostingRegressor(loss="quantile", quantile=0.10, random_state=42, max_iter=100)
    est_p90_t2 = HistGradientBoostingRegressor(loss="quantile", quantile=0.90, random_state=42, max_iter=100)

    est_p50_t2.fit(X_train_t2, y_train_t2)
    est_p10_t2.fit(X_train_t2, y_train_t2)
    est_p90_t2.fit(X_train_t2, y_train_t2)

    X_test_t2 = df_test[FEATURE_COLS_T2].values
    pred_d_t2 = np.maximum(0.0, est_p50_t2.predict(X_test_t2))
    p10_d_t2 = np.maximum(0.0, est_p10_t2.predict(X_test_t2))
    p90_d_t2 = np.maximum(p10_d_t2, est_p90_t2.predict(X_test_t2))

    # Also evaluate the exact order-book forecast
    pred_book_t2 = df_test["units_due_tomorrow_on_books"].values

    metrics_t2 = {
        "model_a_naive": compute_metrics(y_test_t2, pred_a_t2),
        "model_b_weekday": compute_metrics(y_test_t2, pred_b_t2),
        "model_c_rolling7": compute_metrics(y_test_t2, pred_c_t2),
        "model_d_gbdt": compute_metrics(y_test_t2, pred_d_t2, p10_d_t2, p90_d_t2),
        "model_order_book": compute_metrics(y_test_t2, pred_book_t2, pred_book_t2, pred_book_t2)
    }

    # ──────────────────────────────────────────────────────────────────────────
    # SHORTAGE RISK EVALUATION (Pre-Registered Rule)
    # ──────────────────────────────────────────────────────────────────────────
    # Projected Buffer = fg_stock + planned_prod_next - pred_t2
    # High: buffer < 0
    # Medium: buffer < safety_stock (25 units total: 15 for 201 + 10 for 202)
    # Low: otherwise
    # Ground truth: customer backlog > 0 on test days
    fg_test = df_test["fg_stock"].values
    plan_test = df_test["planned_prod_next"].values
    t2_point_forecast = pred_book_t2 if metrics_t2["model_order_book"]["wape"] <= metrics_t2["model_d_gbdt"]["wape"] else pred_d_t2

    projected_buffer = fg_test + plan_test - t2_point_forecast
    safety_stock_threshold = 25.0

    risk_levels = []
    for buf in projected_buffer:
        if buf < 0:
            risk_levels.append("HIGH")
        elif buf < safety_stock_threshold:
            risk_levels.append("MEDIUM")
        else:
            risk_levels.append("LOW")

    actual_backlog_next = df_test["open_customer_backlog"].values > 0
    pred_shortage_alert = np.array([r in ("HIGH", "MEDIUM") for r in risk_levels])

    # Confusion matrix
    tp = int(np.sum(pred_shortage_alert & actual_backlog_next))
    fp = int(np.sum(pred_shortage_alert & (~actual_backlog_next)))
    fn = int(np.sum((~pred_shortage_alert) & actual_backlog_next))
    tn = int(np.sum((~pred_shortage_alert) & (~actual_backlog_next)))

    precision = round(tp / (tp + fp), 4) if (tp + fp) > 0 else 0.0
    recall = round(tp / (tp + fn), 4) if (tp + fn) > 0 else 0.0

    shortage_eval = {
        "rule_definition": "High if fg_stock + planned_prod - T2_forecast < 0; Medium if < safety_stock (25); Low otherwise",
        "sample_size_days": len(df_test),
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "true_negatives": tn,
        "precision": precision,
        "recall": recall,
        "high_risk_count": int(sum(1 for r in risk_levels if r == "HIGH")),
        "medium_risk_count": int(sum(1 for r in risk_levels if r == "MEDIUM")),
        "low_risk_count": int(sum(1 for r in risk_levels if r == "LOW")),
    }

    full_results = {
        "evaluation_period": {
            "train": "2025-01-01 to 2025-06-30 (181 days)",
            "test": "2025-07-01 to 2025-12-31 (184 days)"
        },
        "target_1_new_sales": metrics_t1,
        "target_2_due_tomorrow": metrics_t2,
        "shortage_risk_evaluation": shortage_eval
    }

    # Save to metrics.json
    with open(METRICS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(full_results, f, indent=2)

    return full_results


if __name__ == "__main__":
    results = run_walk_forward_evaluation()
    print("\n" + "=" * 60)
    print("SAGE Next-Day Forecast Walk-Forward Evaluation Results")
    print("=" * 60)
    print(json.dumps(results, indent=2))
