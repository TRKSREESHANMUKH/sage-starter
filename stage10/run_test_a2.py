"""
stage10/run_test_a2.py — SAGE Real-World Generalisation Evaluation: Test A2.

Pre-registered Site-Calibrated Deployment Protocol:
1. Site Baseline Calibration:
   - For each seed, recalibrate the empirical 95th percentile null threshold (S_p95)
     on that seed's own 365-day baseline panel only (zero incident data, zero ground truth).
2. Matched Evaluation Windows:
   - Evaluates tight scenario windows (start_date -> end_date + 7 days) matching Stage 7,
     preventing 60-day autoregressive lag accumulation.
3. Scoring & Classification:
   - Pre-registered targets identical to Stage 7.
   - Detectable subset: INC_03, INC_04, INC_06, INC_08.
   - Evaluates false alarm rate across 20 quiet baseline windows.
4. Outputs to stage10/test_a2_results.json and prints comparative summary.
"""

import os
import sys
import json
import time
import pickle
import random
from datetime import date, timedelta
from pathlib import Path
import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import dowhy.gcm as gcm
from simulator.incident_engine import IncidentEngine

STAGE10_DIR = ROOT_DIR / "stage10"
MODEL_PATH = ROOT_DIR / "stage7" / "fitted_causal_model.pkl"

SCENARIOS = [
    "INC_01", "INC_02", "INC_03", "INC_04", "INC_05",
    "INC_06", "INC_07", "INC_08", "INC_09", "INC_10"
]

TARGET_MAP = {
    "INC_01": "material_101_stock",
    "INC_02": "product_201_actual_production",
    "INC_03": "product_201_fg_stock",
    "INC_04": "product_201_actual_production",
    "INC_05": "material_101_stock",
    "INC_06": "product_202_actual_production",
    "INC_07": "material_103_stock",
    "INC_08": "material_103_stock",
    "INC_09": "material_101_stock",
    "INC_10": "product_201_demand_units"
}

TRUE_DRIVERS = {
    "INC_01": ["supplier_1_po_delay_days", "supplier_1_receipt_fill_rate"],
    "INC_02": ["none"],
    "INC_03": ["product_201_demand_units"],
    "INC_04": ["product_201_capacity_shortfall_units"],
    "INC_05": ["supplier_1_po_delay_days", "supplier_2_po_delay_days"],
    "INC_06": ["supplier_2_po_delay_days", "product_202_capacity_shortfall_units"],
    "INC_07": ["supplier_5_receipt_fill_rate"],
    "INC_08": ["supplier_4_po_delay_days"],
    "INC_09": ["supplier_4_po_delay_days"],
    "INC_10": ["month", "weekday"]
}

DETECTABLE_BY_DESIGN = {"INC_03", "INC_04", "INC_06", "INC_08"}


def score_window(causal_model, df_win, base_df, target_node):
    """Scores Method 1 anomaly attribution for target_node over window."""
    shapley_cfg = gcm.shapley.ShapleyConfig(num_subset_samples=50, num_permutations=3)
    anom_cols = [c for c in list(causal_model.graph.nodes) if c in df_win.columns]

    if target_node not in df_win.columns or target_node not in base_df.columns:
        return {}

    mu = base_df[target_node].mean()
    std = base_df[target_node].std()
    std = std if std > 1e-6 else 1.0

    df_z = df_win.copy()
    df_z["_z"] = (df_z[target_node] - mu).abs() / std
    top_samples = df_z.sort_values("_z", ascending=False).head(5)[anom_cols]

    if top_samples.empty:
        return {}

    try:
        scores = gcm.attribute_anomalies(
            causal_model,
            target_node=target_node,
            anomaly_samples=top_samples,
            shapley_config=shapley_cfg
        )
        return {k: float(np.mean(v)) if hasattr(v, "__len__") else float(v) for k, v in scores.items()}
    except Exception as exc:
        return {}


def calibrate_site_null_threshold(causal_model, base_df, targets, seed):
    """
    Computes site-specific 95th percentile null threshold from 20 quiet baseline windows.
    Zero incident data and zero ground truth used.
    """
    print(f"[Seed {seed}] Calibrating site null threshold across quiet baseline windows...", flush=True)
    rng = np.random.default_rng(seed * 77)
    bin_starts = np.linspace(15, 330, 21, dtype=int)
    null_scores = []

    for i in range(20):
        s_idx = bin_starts[i]
        e_idx = min(len(base_df) - 1, s_idx + 14)
        q_win = base_df.iloc[s_idx:e_idx]
        for tgt in set(targets.values()):
            if tgt in base_df.columns:
                sc = score_window(causal_model, q_win, base_df, tgt)
                exog_sc = [abs(v) for k, v in sc.items() if k != tgt and not k.endswith("_lag1")]
                if exog_sc:
                    null_scores.append(max(exog_sc))

    if not null_scores:
        return 0.218006
    p95 = float(np.percentile(null_scores, 95))
    print(f"[Seed {seed}] Site-calibrated p95 null threshold: {p95:.6f} (from {len(null_scores)} quiet evaluations)", flush=True)
    return p95


def run_test_a2():
    print("=" * 70)
    print("SAGE STAGE 10: REAL-WORLD CHECK — TEST A2 (SITE-CALIBRATED)")
    print("=" * 70)

    print(f"Loading frozen Stage 7 causal model from: {MODEL_PATH}")
    with open(MODEL_PATH, "rb") as f:
        loaded = pickle.load(f)
        causal_model = loaded["causal_model"] if isinstance(loaded, dict) and "causal_model" in loaded else loaded

    SEEDS = [7, 11]
    all_results = {
        "metadata": {
            "test": "Test A2 — Site-Calibrated Deployment Protocol",
            "date": date.today().isoformat(),
            "seeds": SEEDS,
            "window_protocol": "tight_incident_window (start_date -> end_date + 7d)"
        },
        "seed_results": {}
    }

    for seed in SEEDS:
        print(f"\n" + "#" * 70, flush=True)
        print(f"EVALUATING SEED {seed} UNDER PROTOCOL A2", flush=True)
        print("#" * 70, flush=True)

        base_pq = STAGE10_DIR / f"daily_panel_seed{seed}_baseline.parquet"
        if not base_pq.exists():
            print(f"[ERROR] Baseline panel missing: {base_pq}", flush=True)
            continue
        base_df = pd.read_parquet(base_pq)

        # 1. Recalibrate null threshold on this seed's baseline panel only
        site_null = calibrate_site_null_threshold(causal_model, base_df, TARGET_MAP, seed)

        # 2. Incident timing from IncidentEngine
        eng = IncidentEngine()
        eng.seed = seed
        eng.rng = random.Random(seed)
        incidents = {inc["id"]: inc for inc in eng.generate()}

        scenario_evals = []
        detectable_detected = 0

        # 3. Score scenarios on tight windows
        for sc_id in SCENARIOS:
            inc_info = incidents[sc_id]
            start_d = inc_info["start_date"]
            end_d = inc_info["end_date"]
            target = TARGET_MAP[sc_id]
            true_drv_list = TRUE_DRIVERS[sc_id]

            sc_pq = STAGE10_DIR / f"daily_panel_seed{seed}_{sc_id}.parquet"
            if not sc_pq.exists():
                print(f"[ERROR] Scenario panel missing: {sc_pq}", flush=True)
                continue
            iso_df = pd.read_parquet(sc_pq)

            # Tight window: start_date to end_date + 7 days
            start_str = start_d.isoformat()
            win_end = min(date(2025, 12, 31), end_d + timedelta(days=7)).isoformat()
            win_df = iso_df[(iso_df["date"] >= start_str) & (iso_df["date"] <= win_end)]

            scores = score_window(causal_model, win_df, base_df, target)

            # Sort exogenous drivers (excluding self target and lag state)
            sorted_drivers = sorted(
                [(k, v) for k, v in scores.items() if k != target and not k.endswith("_lag1")],
                key=lambda x: abs(x[1]),
                reverse=True
            )

            true_rank = 99
            true_score = 0.0
            for rank_idx, (drv_name, drv_val) in enumerate(sorted_drivers, start=1):
                if any(td in drv_name for td in true_drv_list):
                    true_rank = rank_idx
                    true_score = drv_val
                    break

            top_drv_name = sorted_drivers[0][0] if sorted_drivers else "None"
            top_drv_val = sorted_drivers[0][1] if sorted_drivers else 0.0

            is_detected = (abs(true_score) > site_null) and (true_rank <= 3)

            if sc_id in DETECTABLE_BY_DESIGN and is_detected:
                detectable_detected += 1

            status_str = "DETECTED" if is_detected else "BELOW NULL / UNATTRIBUTED"
            if sc_id in ("INC_02", "INC_10"):
                status_str = "CORRECT REJECTION (CONTROL)" if not is_detected else "FALSE POSITIVE"

            scenario_evals.append({
                "scenario_id": sc_id,
                "type": inc_info["type"],
                "window": f"{start_str} -> {win_end}",
                "target_node": target,
                "true_drivers": true_drv_list,
                "true_driver_score": round(true_score, 4),
                "true_driver_rank": true_rank,
                "top_driver": top_drv_name,
                "top_score": round(top_drv_val, 4),
                "site_null_threshold": round(site_null, 6),
                "cleared_null": bool(abs(true_score) > site_null),
                "classification": status_str
            })

            print(f"  [{sc_id}] Tight Win: {start_str}->{win_end} | True rank: {true_rank}, Score: {true_score:.4f} (Site Null: {site_null:.4f}) -> {status_str}", flush=True)

        # 4. False alarm rate on 20 quiet windows
        print(f"[Seed {seed}] Scoring 20 Quiet Windows for False Alarm Rate...", flush=True)
        bin_starts = np.linspace(15, 330, 21, dtype=int)
        false_alarms = 0
        quiet_evals = []

        for i in range(20):
            s_idx = bin_starts[i]
            e_idx = min(len(base_df) - 1, s_idx + 14)
            w_df = base_df.iloc[s_idx:e_idx]
            w_start = w_df["date"].iloc[0]
            w_end = w_df["date"].iloc[-1]

            target = TARGET_MAP[SCENARIOS[i % len(SCENARIOS)]]
            sc = score_window(causal_model, w_df, base_df, target)
            exog_sc = [abs(v) for k, v in sc.items() if k != target and not k.endswith("_lag1")]
            max_v = max(exog_sc) if exog_sc else 0.0

            is_fa = bool(max_v > site_null)
            if is_fa:
                false_alarms += 1

            quiet_evals.append({
                "window": f"{w_start} -> {w_end}",
                "target": target,
                "max_score": round(max_v, 4),
                "false_alarm": is_fa
            })

        detection_rate = round((detectable_detected / len(DETECTABLE_BY_DESIGN)) * 100, 1)
        fa_rate = round((false_alarms / 20) * 100, 1)

        print(f"[Seed {seed} A2 Summary] Detectable: {detectable_detected}/{len(DETECTABLE_BY_DESIGN)} ({detection_rate}%), False Alarms: {false_alarms}/20 ({fa_rate}%)", flush=True)

        all_results["seed_results"][f"seed_{seed}"] = {
            "seed": seed,
            "site_null_threshold": round(site_null, 6),
            "detectable_scenarios_evaluated": len(DETECTABLE_BY_DESIGN),
            "detectable_detected": detectable_detected,
            "detection_rate_pct": detection_rate,
            "quiet_windows_evaluated": 20,
            "false_alarms_count": false_alarms,
            "false_alarm_rate_pct": fa_rate,
            "scenario_evaluations": scenario_evals,
            "quiet_window_evaluations": quiet_evals
        }

    out_file = STAGE10_DIR / "test_a2_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)
    print(f"\n[Test A2] Completed! Results written to: {out_file}", flush=True)


if __name__ == "__main__":
    run_test_a2()
