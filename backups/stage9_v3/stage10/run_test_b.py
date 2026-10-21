"""
stage10/run_test_b.py — SAGE Real-World Generalisation Evaluation: Test B.

Plausibility check on the demand side using a real public retail dataset:
- Uses the Walmart Store Sales Forecasting dataset (Store 1, Department 72: Consumer Electronics).
- Fits the calendar -> demand relationship on Year 1 (2010 historical baseline).
- Scores Year 2 (2011) which contains documented real-world retail disruptions:
  Thanksgiving / Black Friday, Super Bowl, Labor Day, and Christmas holiday weeks.
- The known calendar events are the ground truth "answer key".
- Calibrates empirical null threshold from ordinary non-holiday weeks (Stage 7 p95 method).
- Tests whether attribution scores flag those real events significantly more than ordinary days.
- Saves results to stage10/test_b_results.json.
"""

import os
import sys
import json
import urllib.request
import io
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

ROOT_DIR = Path(__file__).resolve().parent.parent
STAGE10_DIR = ROOT_DIR / "stage10"
DATA_DIR = STAGE10_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

WALMART_URL = "https://raw.githubusercontent.com/keertisuryawanshi/Walmart-Store-sales-Forecasting/main/Walmart-code/datasets/train.csv"
LOCAL_CSV = DATA_DIR / "walmart_train.csv"


def download_or_load_dataset() -> pd.DataFrame:
    """Downloads or loads cached Walmart store sales dataset."""
    if LOCAL_CSV.exists():
        print(f"Loading cached Walmart dataset from {LOCAL_CSV}...")
        return pd.read_csv(LOCAL_CSV)

    print(f"Downloading Walmart dataset from {WALMART_URL}...")
    req = urllib.request.Request(WALMART_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        content = resp.read()
    with open(LOCAL_CSV, "wb") as f:
        f.write(content)
    print(f"Saved dataset to {LOCAL_CSV} ({len(content)} bytes)")
    return pd.read_csv(io.BytesIO(content))


def run_test_b():
    print("=" * 70)
    print("SAGE STAGE 10: REAL-WORLD CHECK — TEST B (REAL DEMAND DATASET)")
    print("=" * 70)

    try:
        df_raw = download_or_load_dataset()
    except Exception as exc:
        print(f"Network error or download failed: {exc}")
        return {
            "status": "skipped",
            "reason": f"Network access unavailable: {exc}"
        }

    # Store 1, Department 72 (Consumer Electronics / Seasonal Surge)
    df = df_raw[(df_raw["Store"] == 1) & (df_raw["Dept"] == 72)].copy()
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values("Date").reset_index(drop=True)

    print(f"Loaded Store 1, Dept 72 series: {len(df)} weekly observations ({df['Date'].min().date()} to {df['Date'].max().date()})")

    # Calendar features matching SAGE expert DAG
    df["month"] = df["Date"].dt.month
    df["week_of_year"] = df["Date"].dt.isocalendar().week.astype(int)
    df["is_holiday"] = df["IsHoliday"].astype(int)
    df["sales"] = df["Weekly_Sales"].astype(float)

    # Train / Test split:
    # Train: Year 1 (2010)
    # Test : Year 2 (2011, containing Super Bowl, Labor Day, Black Friday, Christmas)
    train_df = df[df["Date"] < "2011-01-01"].copy()
    test_df = df[(df["Date"] >= "2011-01-01") & (df["Date"] < "2012-01-01")].copy()

    print(f"Calibration Split (Year 1: 2010): {len(train_df)} weeks ({train_df['Date'].min().date()} to {train_df['Date'].max().date()})")
    print(f"Evaluation Split  (Year 2: 2011): {len(test_df)} weeks ({test_df['Date'].min().date()} to {test_df['Date'].max().date()})")

    # Fit calendar -> demand mechanism on baseline non-holiday pattern
    # Standard ordinary business weeks used to learn non-event baseline
    train_baseline = train_df[train_df["is_holiday"] == 0]
    baseline_sales = float(train_baseline["sales"].mean())
    baseline_std = float(train_baseline["sales"].std())

    # Regression on calendar indicators
    feature_cols = ["month"]
    X_train = pd.get_dummies(train_baseline[feature_cols], columns=["month"], drop_first=True)
    y_train = train_baseline["sales"]

    model = Ridge(alpha=10.0)
    model.fit(X_train, y_train)

    train_preds = model.predict(X_train)
    train_resids = np.abs(y_train - train_preds)

    # Stage 7 Stratified Empirical Null Calibration (p95 on non-holiday baseline)
    null_p95 = float(np.percentile(train_resids, 95))
    null_mean = float(np.mean(train_resids))

    print(f"\nEmpirical Null Calibration on Ordinary Non-Holiday Weeks:")
    print(f"  Baseline Mean Sales        : ${baseline_sales:,.2f}")
    print(f"  Mean Ordinary Deviation    : ${null_mean:,.2f}")
    print(f"  p95 Null Bound (S_p95)     : ${null_p95:,.2f}")

    # Evaluate Year 2 Test Period
    X_test = pd.get_dummies(test_df[feature_cols], columns=["month"], drop_first=True)
    X_test = X_test.reindex(columns=X_train.columns, fill_value=0)

    test_preds = model.predict(X_test)
    test_resids = np.abs(test_df["sales"] - test_preds)

    test_df["predicted_sales"] = test_preds
    test_df["anomaly_score"] = test_resids
    test_df["cleared_null"] = test_resids > null_p95

    # Known calendar events (documented answer key)
    holiday_events = test_df[test_df["is_holiday"] == 1].copy()
    ordinary_weeks = test_df[test_df["is_holiday"] == 0].copy()

    total_events = len(holiday_events)
    events_cleared = int(holiday_events["cleared_null"].sum())
    event_detection_rate = (events_cleared / total_events * 100.0) if total_events > 0 else 0.0

    total_ordinary = len(ordinary_weeks)
    ordinary_false_alarms = int(ordinary_weeks["cleared_null"].sum())
    ordinary_false_alarm_rate = (ordinary_false_alarms / total_ordinary * 100.0) if total_ordinary > 0 else 0.0

    mean_event_score = float(holiday_events["anomaly_score"].mean())
    mean_ordinary_score = float(ordinary_weeks["anomaly_score"].mean())
    signal_to_noise = (mean_event_score / mean_ordinary_score) if mean_ordinary_score > 0 else 0.0

    print(f"\nEvaluation Results on Year 2 Known Events:")
    print(f"  Documented Ground-Truth Events : {total_events}")
    print(f"  Events Cleared Null (p95)      : {events_cleared}/{total_events} ({event_detection_rate:.1f}%)")
    print(f"  Ordinary Non-Holiday Weeks     : {total_ordinary}")
    print(f"  False Alarms on Ordinary Weeks : {ordinary_false_alarms}/{total_ordinary} ({ordinary_false_alarm_rate:.1f}%)")
    print(f"  Mean Event Attribution Score   : ${mean_event_score:,.2f}")
    print(f"  Mean Ordinary Week Score       : ${mean_ordinary_score:,.2f}")
    print(f"  Signal-to-Noise Ratio          : {signal_to_noise:.2f}x")

    event_details = []
    print(f"\nBreakdown of Documented Event Weeks:")
    for _, row in holiday_events.iterrows():
        dt_str = row["Date"].strftime("%Y-%m-%d")
        if "-02-" in dt_str:
            event_name = "Super Bowl"
        elif "-09-" in dt_str:
            event_name = "Labor Day"
        elif "-11-" in dt_str:
            event_name = "Thanksgiving / Black Friday"
        elif "-12-" in dt_str:
            event_name = "Christmas"
        else:
            event_name = "Holiday Event"
        status_lbl = "FLAGGED ABOVE NULL" if row["cleared_null"] else "WITHIN NULL"
        event_details.append({
            "date": dt_str,
            "event_name": event_name,
            "actual_sales": round(float(row["sales"]), 2),
            "expected_baseline": round(float(row["predicted_sales"]), 2),
            "attribution_score": round(float(row["anomaly_score"]), 2),
            "cleared_null_p95": bool(row["cleared_null"]),
            "status": status_lbl
        })
        print(f"  • {dt_str} [{event_name}]: Actual=${row['sales']:,.2f}, Expected=${row['predicted_sales']:,.2f}, Score=${row['anomaly_score']:,.2f} -> {status_lbl}")

    results = {
        "status": "completed",
        "dataset": "Walmart Store Sales Forecasting (Store 1, Dept 72: Consumer Electronics)",
        "scope": "Demand-side calendar plausibility check only; does not evaluate supply chain or inventory mechanisms.",
        "calibration_period": {
            "period": "2010 (Year 1)",
            "start": train_df["Date"].min().strftime("%Y-%m-%d"),
            "end": train_df["Date"].max().strftime("%Y-%m-%d"),
            "weeks_count": len(train_df),
            "null_p95_threshold": round(null_p95, 2),
            "null_mean_deviation": round(null_mean, 2)
        },
        "evaluation_period": {
            "period": "2011 (Year 2)",
            "start": test_df["Date"].min().strftime("%Y-%m-%d"),
            "end": test_df["Date"].max().strftime("%Y-%m-%d"),
            "weeks_count": len(test_df),
            "documented_holiday_events_count": total_events,
            "holiday_detection_rate_pct": round(event_detection_rate, 1),
            "ordinary_weeks_count": total_ordinary,
            "ordinary_weeks_false_alarm_rate_pct": round(ordinary_false_alarm_rate, 1),
            "mean_event_attribution_score": round(mean_event_score, 2),
            "mean_ordinary_attribution_score": round(mean_ordinary_score, 2),
            "signal_to_noise_ratio": round(signal_to_noise, 2),
            "event_details": event_details
        }
    }

    out_file = STAGE10_DIR / "test_b_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\nSaved Test B results to: {out_file}")
    return results


if __name__ == "__main__":
    run_test_b()
