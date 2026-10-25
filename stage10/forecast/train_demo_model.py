"""
stage10/forecast/train_demo_model.py — Train and freeze fixed production forecast model on all of 2025.
"""

from __future__ import annotations

import hashlib
import pickle
import sys
from datetime import date
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from stage10.forecast.data import build_feature_dataset
from stage10.forecast.models import FEATURE_COLS_T1, FEATURE_COLS_T2

MODEL_PKL_PATH = ROOT_DIR / "stage10" / "forecast" / "model.pkl"
PREREG_PATH = ROOT_DIR / "stage10" / "prereg_forecast.md"


def train_and_freeze_demo_model() -> str:
    print("Building full 2025 feature dataset...")
    df = build_feature_dataset(start_date=date(2025, 1, 1), end_date=date(2025, 12, 31))

    X_t1 = df[FEATURE_COLS_T1].values
    y_t1 = df["T1_target"].values

    print(f"Fitting final models on {len(df)} days...")
    # T1 Models (Quantile GBDT)
    est_p50_t1 = HistGradientBoostingRegressor(loss="quantile", quantile=0.50, random_state=42, max_iter=100)
    est_p10_t1 = HistGradientBoostingRegressor(loss="quantile", quantile=0.10, random_state=42, max_iter=100)
    est_p90_t1 = HistGradientBoostingRegressor(loss="quantile", quantile=0.90, random_state=42, max_iter=100)

    est_p50_t1.fit(X_t1, y_t1)
    est_p10_t1.fit(X_t1, y_t1)
    est_p90_t1.fit(X_t1, y_t1)

    # T2 Models (Quantile GBDT)
    X_t2 = df[FEATURE_COLS_T2].values
    y_t2 = df["T2_target"].values

    est_p50_t2 = HistGradientBoostingRegressor(loss="quantile", quantile=0.50, random_state=42, max_iter=100)
    est_p10_t2 = HistGradientBoostingRegressor(loss="quantile", quantile=0.10, random_state=42, max_iter=100)
    est_p90_t2 = HistGradientBoostingRegressor(loss="quantile", quantile=0.90, random_state=42, max_iter=100)

    est_p50_t2.fit(X_t2, y_t2)
    est_p10_t2.fit(X_t2, y_t2)
    est_p90_t2.fit(X_t2, y_t2)

    # Compute empirical residuals for fallback model (b) on full 2025
    res_b_t1 = y_t1 - df["t1_lag_7"].values
    res_p10_b = float(np.percentile(res_b_t1, 10))
    res_p90_b = float(np.percentile(res_b_t1, 90))

    artifact = {
        "description": "SAGE Frozen Production Forecast Model (Trained on 2025 full year)",
        "train_period": "2025-01-01 to 2025-12-31 (365 days)",
        "feature_cols_t1": FEATURE_COLS_T1,
        "feature_cols_t2": FEATURE_COLS_T2,
        "t1_p50": est_p50_t1,
        "t1_p10": est_p10_t1,
        "t1_p90": est_p90_t1,
        "t2_p50": est_p50_t2,
        "t2_p10": est_p10_t2,
        "t2_p90": est_p90_t2,
        "fallback_b_res_p10": res_p10_b,
        "fallback_b_res_p90": res_p90_b
    }

    with open(MODEL_PKL_PATH, "wb") as f:
        pickle.dump(artifact, f)

    with open(MODEL_PKL_PATH, "rb") as f:
        sha256 = hashlib.sha256(f.read()).hexdigest()

    print(f"Model saved to {MODEL_PKL_PATH}")
    print(f"SHA256: {sha256}")

    # Update prereg_forecast.md with SHA256
    if PREREG_PATH.exists():
        content = PREREG_PATH.read_text(encoding="utf-8")
        if "[MODEL_DIGEST_PLACEHOLDER]" in content:
            new_content = content.replace(
                "[MODEL_DIGEST_PLACEHOLDER]",
                f"**Frozen Model File:** `stage10/forecast/model.pkl`  \n"
                f"**SHA256 Checksum:** `{sha256}`  \n"
                f"**Training Period:** 2025-01-01 to 2025-12-31 (365 days)  \n"
                f"**Parameters:** 100 trees, max depth default, quantile loss (p10, p50, p90)"
            )
            PREREG_PATH.write_text(new_content, encoding="utf-8")
            print("Updated prereg_forecast.md with model SHA256 digest.")

    return sha256


if __name__ == "__main__":
    train_and_freeze_demo_model()
