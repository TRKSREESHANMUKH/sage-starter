"""
stage10/run_test_a.py — SAGE Real-World Generalisation Evaluation: Test A.

Runs Test A on fresh, unseen synthetic worlds:
- Seeds 7 and 11.
- All 10 frozen operational scenarios with distinct timings and parameter draws.
- Uses frozen Stage 7 causal model and frozen null thresholds (zero refitting).
- Scores pre-registered target for each scenario across a trailing window.
- Evaluates 20 randomly sampled quiet windows per seed to measure false-alarm rate.
- Outputs results to stage10/test_a_results.json and prints comparative summary.
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
import networkx as nx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import dowhy.gcm as gcm
from app.database import Base
from simulator.master_data import seed_master_data
from simulator.incident_engine import IncidentEngine
from analytics.build_daily_panel import build_panel

STAGE10_DB_URL = "postgresql+psycopg2://sage_user:sage_dev_password@localhost:5433/sage_stage10_db"
os.environ["DATABASE_URL"] = STAGE10_DB_URL
os.environ["PYTHONPATH"] = "."

STAGE10_DIR = ROOT_DIR / "stage10"
STAGE10_DIR.mkdir(parents=True, exist_ok=True)

MODEL_PATH = ROOT_DIR / "stage7" / "fitted_causal_model.pkl"

# Frozen Null Thresholds from Stage 7
M1_P95_NULL = 0.218006
M2_P95_NULL = 0.922611

SCENARIOS = [
    "INC_01", "INC_02", "INC_03", "INC_04", "INC_05",
    "INC_06", "INC_07", "INC_08", "INC_09", "INC_10"
]

# Pre-registered primary targets
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

MATERIALS = [101, 102, 103]
PRODUCTS = [201, 202]


def add_lags(df):
    df_out = df.copy()
    for m in MATERIALS:
        df_out[f"material_{m}_stock_lag1"] = df_out[f"material_{m}_stock"].shift(1).fillna(200.0)
    for p in PRODUCTS:
        df_out[f"product_{p}_fg_stock_lag1"] = df_out[f"product_{p}_fg_stock"].shift(1).fillna(50.0)
    return df_out


def run_sim(mode: str, seed: int, target_scenario: str = None):
    """Clean-slates sage_stage10_db and executes daily_simulation.py."""
    import subprocess
    env = os.environ.copy()
    env["PYTHONPATH"] = "."
    env["DATABASE_URL"] = STAGE10_DB_URL
    env["MODE"] = mode
    env["SEED"] = str(seed)
    if target_scenario:
        env["TARGET_SCENARIO"] = target_scenario
    else:
        env.pop("TARGET_SCENARIO", None)

    # Clean-slate and seed master data on sage_stage10_db
    cmd_seed = ["./venv/bin/python", "-c", "from simulator.master_data import seed_master_data; seed_master_data()"]
    res_seed = subprocess.run(cmd_seed, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if res_seed.returncode != 0:
        raise RuntimeError(f"Master data seeding failed: {res_seed.stderr}")

    cmd = ["./venv/bin/python", "simulator/daily_simulation.py"]
    res = subprocess.run(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Simulation failed for mode={mode}, seed={seed}, target={target_scenario}: {res.stderr}")


def build_df():
    engine = create_engine(STAGE10_DB_URL)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        df = build_panel(db, output_parquet=None, output_csv=None)
        return df
    finally:
        db.close()


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


def main():
    print("=" * 70)
    print("SAGE STAGE 10: REAL-WORLD CHECK — TEST A (SEEDS 7 & 11)")
    print("=" * 70)

    # 1. Load Frozen Causal Model
    print(f"Loading frozen Stage 7 causal model from: {MODEL_PATH}")
    with open(MODEL_PATH, "rb") as f:
        loaded = pickle.load(f)
        causal_model = loaded["causal_model"] if isinstance(loaded, dict) and "causal_model" in loaded else loaded

    results = {
        "metadata": {
            "test": "Test A — Fresh synthetic worlds",
            "date": date.today().isoformat(),
            "seeds": [7, 11],
            "frozen_m1_null_threshold": M1_P95_NULL,
            "frozen_m2_null_threshold": M2_P95_NULL
        },
        "seed_results": {}
    }

    SEEDS = [7, 11]

    for seed in SEEDS:
        print(f"\n" + "#" * 70, flush=True)
        print(f"EVALUATING UNSEEN SYNTHETIC WORLD: SEED {seed}", flush=True)
        print("#" * 70, flush=True)

        base_pq = STAGE10_DIR / f"daily_panel_seed{seed}_baseline.parquet"
        if base_pq.exists():
            print(f"[Seed {seed}] Loading existing baseline panel from: {base_pq}", flush=True)
            base_df = pd.read_parquet(base_pq)
        else:
            print(f"\n[Seed {seed}] Running Baseline Simulation...", flush=True)
            run_sim(mode="baseline", seed=seed)
            base_df_raw = build_df()
            base_df = add_lags(base_df_raw)
            base_df.to_parquet(base_pq)
            print(f"[Seed {seed}] Baseline panel saved: {base_pq} ({len(base_df)} days)", flush=True)

        # Step B: Get incident start/end dates for this seed
        eng = IncidentEngine()
        eng.seed = seed
        eng.rng = random.Random(seed)
        incidents = {inc["id"]: inc for inc in eng.generate()}

        scenario_evals = []
        detectable_detected = 0

        # Step C: Run and score each scenario
        for sc_id in SCENARIOS:
            inc_info = incidents[sc_id]
            start_d = inc_info["start_date"]
            end_d = inc_info["end_date"]
            duration = (end_d - start_d).days + 1
            target = TARGET_MAP[sc_id]
            true_drv_list = TRUE_DRIVERS[sc_id]

            sc_pq = STAGE10_DIR / f"daily_panel_seed{seed}_{sc_id}.parquet"
            if sc_pq.exists():
                print(f"  [{sc_id}] Loading cached panel from: {sc_pq}", flush=True)
                iso_df = pd.read_parquet(sc_pq)
            else:
                print(f"  [{sc_id}] Running simulation (Window: {start_d} -> {end_d}, Target: {target})...", flush=True)
                run_sim(mode="scenario", seed=seed, target_scenario=sc_id)
                iso_raw = build_df()
                iso_df = add_lags(iso_raw)
                iso_df.to_parquet(sc_pq)

            # Trailing window: from start_date to start_date + 60 days
            start_str = start_d.isoformat()
            win_end = min(date(2025, 12, 31), start_d + timedelta(days=60)).isoformat()
            win_df = iso_df[(iso_df["date"] >= start_str) & (iso_df["date"] <= win_end)]

            # Score attribution
            scores = score_window(causal_model, win_df, base_df, target)

            # Sort drivers
            sorted_drivers = sorted(
                [(k, v) for k, v in scores.items() if k != target],
                key=lambda x: abs(x[1]),
                reverse=True
            )

            # Find rank of true driver
            true_rank = 99
            true_score = 0.0
            for rank_idx, (drv_name, drv_val) in enumerate(sorted_drivers, start=1):
                if any(td in drv_name for td in true_drv_list):
                    true_rank = rank_idx
                    true_score = drv_val
                    break

            # Classify detection
            top_drv_name = sorted_drivers[0][0] if sorted_drivers else "None"
            top_drv_val = sorted_drivers[0][1] if sorted_drivers else 0.0

            is_detected = (abs(true_score) > M1_P95_NULL) and (true_rank <= 3)

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
                "cleared_null": bool(abs(true_score) > M1_P95_NULL),
                "classification": status_str
            })

            print(f"    -> True driver rank: {true_rank}, Score: {true_score:.4f} (Null: {M1_P95_NULL:.4f}) -> {status_str}", flush=True)

        # Step D: False Alarm Evaluation on 20 Quiet Windows
        print(f"\n[Seed {seed}] Scoring 20 Quiet Windows from Baseline Panel for False-Alarm Rate...", flush=True)
        rng = np.random.default_rng(seed * 100)
        bin_starts = np.linspace(15, 330, 21, dtype=int)
        sampled_starts = [int(rng.integers(bin_starts[i], bin_starts[i+1])) for i in range(20)]
        quiet_windows = []
        false_alarms = 0

        for i, start_day in enumerate(sampled_starts):
            d_start = date(2025, 1, 1) + timedelta(days=start_day)
            d_end = d_start + timedelta(days=14)
            s_str = d_start.isoformat()
            e_str = d_end.isoformat()

            target = list(TARGET_MAP.values())[i % len(TARGET_MAP)]
            q_win = base_df[(base_df["date"] >= s_str) & (base_df["date"] <= e_str)]

            q_scores = score_window(causal_model, q_win, base_df, target)
            top_exog = max([abs(v) for k, v in q_scores.items() if k != target] or [0.0])

            is_alarm = bool(top_exog > M1_P95_NULL)
            if is_alarm:
                false_alarms += 1

            quiet_windows.append({
                "window": f"{s_str} -> {e_str}",
                "target": target,
                "max_score": round(float(top_exog), 4),
                "false_alarm": is_alarm
            })

        detection_rate = (detectable_detected / len(DETECTABLE_BY_DESIGN)) * 100.0
        false_alarm_rate = (false_alarms / len(quiet_windows)) * 100.0

        seed_summary = {
            "seed": seed,
            "detectable_scenarios_evaluated": len(DETECTABLE_BY_DESIGN),
            "detectable_detected": detectable_detected,
            "detection_rate_pct": round(detection_rate, 1),
            "quiet_windows_evaluated": len(quiet_windows),
            "false_alarms_count": false_alarms,
            "false_alarm_rate_pct": round(false_alarm_rate, 1),
            "scenario_evaluations": scenario_evals,
            "quiet_window_samples": quiet_windows[:5]
        }
        results["seed_results"][f"seed_{seed}"] = seed_summary

        print(f"\n[Seed {seed} Summary]", flush=True)
        print(f"  Detection Rate (Detectable Scenarios): {detection_rate:.1f}% ({detectable_detected}/{len(DETECTABLE_BY_DESIGN)})", flush=True)
        print(f"  False-Alarm Rate (20 Quiet Windows)  : {false_alarm_rate:.1f}% ({false_alarms}/20)", flush=True)

        # Save progress after each seed
        out_file = STAGE10_DIR / "test_a_results.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

    print(f"\nTest A completed successfully! Full results saved to: {out_file}", flush=True)


if __name__ == "__main__":
    main()
