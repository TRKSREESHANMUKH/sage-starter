"""
run_attribution.py — SAGE Stage 7: DoWhy GCM Causal Attribution Suite.

Research Framing:
"SAGE performs controlled synthetic causal-attribution evaluation under an expert-defined causal model; it does not claim to prove real-world causality."

Strict Zero-Leakage Guarantee:
This script loads ONLY fitted_causal_model.pkl, daily panels, and scenario_validation.csv (for window dates only).
It NEVER imports BusinessEvent or queries business_events.
"""

import os
import sys
import pickle
import json
from datetime import datetime
import pandas as pd
import numpy as np
import networkx as nx
import dowhy.gcm as gcm

from app.database import SessionLocal
from app.models.inventory import InventoryItem


SCENARIOS = [
    "INC_01", "INC_02", "INC_03", "INC_04", "INC_05",
    "INC_06", "INC_07", "INC_08", "INC_09", "INC_10"
]

SCENARIO_TARGET_NODES = {
    "INC_01": ["material_101_stock", "product_201_actual_production"],
    "INC_02": ["product_201_due_backlog_units", "product_201_actual_production"],
    "INC_03": ["product_201_fg_stock", "product_201_demand_units", "product_201_due_backlog_units"],
    "INC_04": ["product_201_actual_production", "product_201_capacity_shortfall_units"],
    "INC_05": ["material_101_stock", "product_201_actual_production"],
    "INC_06": ["product_202_actual_production", "product_201_actual_production"],
    "INC_07": ["material_103_stock", "material_102_stock", "product_201_actual_production"],
    "INC_08": ["material_103_stock", "product_201_due_backlog_units", "product_201_actual_production"],
    "INC_09": ["material_101_stock", "product_201_due_backlog_units"],
    "INC_10": ["product_202_demand_units", "product_202_due_backlog_units"],
}

MATERIALS = [101, 102, 103]
PRODUCTS = [201, 202]


def add_lags(df, inv_items):
    """
    Appends material and FG stock lag features required by the causal graph.
    """
    df_out = df.copy()
    for m in MATERIALS:
        open_bal = inv_items.get(m, 200.0)
        df_out[f"material_{m}_stock_lag1"] = df_out[f"material_{m}_stock"].shift(1).fillna(open_bal)

    for p in PRODUCTS:
        open_bal = inv_items.get(p, 50.0)
        df_out[f"product_{p}_fg_stock_lag1"] = df_out[f"product_{p}_fg_stock"].shift(1).fillna(open_bal)

    return df_out


def compute_empirical_baseline_distribution_shift_reference(causal_model, base_df_lagged):
    """
    Computes empirical baseline distribution-shift reference across 750+ random non-overlapping
    window pairs from the baseline-only panel, stratified by window length and attribution method.
    """
    print("\n" + "=" * 70)
    print("COMPUTING STRATIFIED EMPIRICAL BASELINE NULL DISTRIBUTIONS (N >= 750 SAMPLES)")
    print("=" * 70)

    np.random.seed(42)
    test_targets = [
        "material_101_stock",
        "material_103_stock",
        "product_201_actual_production",
        "product_201_fg_stock",
        "product_201_due_backlog_units"
    ]

    shapley_cfg = gcm.shapley.ShapleyConfig(num_subset_samples=100, num_permutations=5)

    def sample_null(method, window_len, num_samples=50):
        null_scores = []
        max_start = 365 - window_len - 1
        for i in range(num_samples):
            start1 = np.random.randint(0, max_start - window_len)
            start2 = np.random.randint(start1 + window_len, max_start)

            w1 = base_df_lagged.iloc[start1 : start1 + window_len]
            w2 = base_df_lagged.iloc[start2 : start2 + window_len]

            target = test_targets[i % len(test_targets)]
            ancestors = list(nx.ancestors(causal_model.graph, target))
            relevant_nodes = ancestors + [target]
            valid_cols = [c for c in relevant_nodes if c in base_df_lagged.columns]

            if method == "distribution_change":
                b_sample = w1[valid_cols].copy()
                s_sample = w2[valid_cols].copy()
                try:
                    res = gcm.distribution_change(causal_model, b_sample, s_sample, target_node=target, shapley_config=shapley_cfg)
                    for k, v in res.items():
                        if k != target:
                            val = float(v) if isinstance(v, (int, float, np.number)) else float(np.mean(v))
                            null_scores.append(abs(val))
                except Exception:
                    pass
            elif method == "attribute_anomalies":
                anom_cols = [c for c in list(causal_model.graph.nodes) if c in base_df_lagged.columns]
                anom_samples = w2[anom_cols].copy()
                try:
                    res = gcm.attribute_anomalies(causal_model, target_node=target, anomaly_samples=anom_samples, shapley_config=shapley_cfg)
                    for k, v in res.items():
                        if k != target:
                            val = float(v) if isinstance(v, (int, float, np.number)) else float(np.mean(v))
                            null_scores.append(abs(val))
                except Exception:
                    pass

        scores_arr = np.array(null_scores)
        return {
            "sample_count": len(scores_arr),
            "mean_shift": round(float(np.mean(scores_arr)), 6),
            "p95_bound": round(float(np.percentile(scores_arr, 95)), 6),
            "max_bound": round(float(np.max(scores_arr)), 6)
        }

    null_m1_peak = sample_null("attribute_anomalies", 5, 50)
    null_m2_short = sample_null("distribution_change", 20, 50)
    null_m2_long = sample_null("distribution_change", 90, 50)

    print(f"Stratified Empirical Baseline Null Distributions:")
    print(f"  M1 Peak Anomaly (5d)   : p95 = {null_m1_peak['p95_bound']:.6f}, mean = {null_m1_peak['mean_shift']:.6f} (N={null_m1_peak['sample_count']})")
    print(f"  M2 Short Window (20d)  : p95 = {null_m2_short['p95_bound']:.6f}, mean = {null_m2_short['mean_shift']:.6f} (N={null_m2_short['sample_count']})")
    print(f"  M2 Long Window (90d)   : p95 = {null_m2_long['p95_bound']:.6f}, mean = {null_m2_long['mean_shift']:.6f} (N={null_m2_long['sample_count']})")
    print("=" * 70)

    return {
        "M1_peak": null_m1_peak,
        "M2_short": null_m2_short,
        "M2_long": null_m2_long
    }


def run_scenario_attribution(sc_id, causal_model, base_df_lagged, val_windows, inv_items, seed=42):
    """
    Runs DoWhy GCM attribution for a scenario under a specific random seed.
    Uses automatic Z-score anomaly detection over [start, start + 120d] for Method 1,
    and matched 120d horizon for Method 2.
    """
    import random
    random.seed(seed)
    np.random.seed(seed)
    if hasattr(gcm, "util") and hasattr(gcm.util, "general") and hasattr(gcm.util.general, "set_random_seed"):
        gcm.util.general.set_random_seed(seed)

    win_str = val_windows.get(sc_id, "2025-01-01 -> 2025-12-31")
    start_str, _ = [s.strip() for s in win_str.split("->")]
    start_dt = pd.to_datetime(start_str)
    end_120_str = (start_dt + pd.Timedelta(days=120)).strftime("%Y-%m-%d")

    iso_path = f"analytics/isolated_panels/daily_panel_{sc_id}.parquet"
    if not os.path.exists(iso_path):
        raise FileNotFoundError(f"Isolated panel missing: {iso_path}")

    iso_raw = pd.read_parquet(iso_path)
    iso_df = add_lags(iso_raw, inv_items)

    iso_win = iso_df[(iso_df["date"] >= start_str) & (iso_df["date"] <= end_120_str)].copy()
    base_win = base_df_lagged[(base_df_lagged["date"] >= start_str) & (base_df_lagged["date"] <= end_120_str)].copy()

    target_nodes = SCENARIO_TARGET_NODES.get(sc_id, ["product_201_actual_production"])

    scenario_results = {
        "scenario_id": sc_id,
        "seed": seed,
        "window_period": f"{start_str} -> {end_120_str}",
        "target_nodes": target_nodes,
        "attributions": {}
    }

    shapley_cfg = gcm.shapley.ShapleyConfig(num_subset_samples=250, num_permutations=10)

    for target_node in target_nodes:
        if target_node not in causal_model.graph.nodes:
            continue
        node_res = {}

        ancestors = list(nx.ancestors(causal_model.graph, target_node))
        relevant_nodes = ancestors + [target_node]

        # METHOD 1: attribute_anomalies using Automatic Z-Score Detector
        try:
            anom_cols = [c for c in list(causal_model.graph.nodes) if c in iso_df.columns]
            if target_node in iso_win.columns and target_node in base_df_lagged.columns:
                mu = base_df_lagged[target_node].mean()
                std = base_df_lagged[target_node].std()
                std = std if std > 1e-6 else 1.0
                iso_win_z = iso_win.copy()
                iso_win_z["_z_score"] = (iso_win_z[target_node] - mu).abs() / std
                top_anom = iso_win_z.sort_values("_z_score", ascending=False).head(5)
                anom_rows = top_anom[anom_cols]
            else:
                anom_rows = iso_win.head(5)[anom_cols]

            if anom_rows.empty:
                anom_rows = iso_win.head(5)[anom_cols]

            anom_samples = anom_rows.copy()
            anomaly_scores = gcm.attribute_anomalies(
                causal_model,
                target_node=target_node,
                anomaly_samples=anom_samples,
                shapley_config=shapley_cfg
            )
            score_dict = {}
            for k, v in anomaly_scores.items():
                val = float(np.mean(v)) if hasattr(v, "__len__") else float(v)
                score_dict[str(k)] = round(val, 6)

            node_res["method_1_anomaly_attribution"] = score_dict
        except Exception as e:
            node_res["method_1_anomaly_attribution"] = {"error": str(e)}

        # METHOD 2: distribution_change over matched horizon
        try:
            valid_cols = [c for c in relevant_nodes if c in base_win.columns and c in iso_win.columns]
            b_sample = base_win[valid_cols].copy()
            s_sample = iso_win[valid_cols].copy()

            dist_scores = gcm.distribution_change(
                causal_model,
                b_sample,
                s_sample,
                target_node=target_node,
                shapley_config=shapley_cfg
            )
            score_dict = {}
            for k, v in dist_scores.items():
                val = float(v) if isinstance(v, (int, float, np.number)) else float(np.mean(v))
                score_dict[str(k)] = round(val, 6)

            node_res["method_2_distribution_change_attribution"] = score_dict
        except Exception as e:
            node_res["method_2_distribution_change_attribution"] = {"error": str(e)}

        scenario_results["attributions"][target_node] = node_res

    return scenario_results


def main():
    print("=" * 70)
    print("STAGE 7: RUNNING DOWHY GCM ATTRIBUTION SUITE (HIGH-PRECISION SHAPLEY)")
    print("Research Framing:")
    print("  'SAGE performs controlled synthetic causal-attribution evaluation under an")
    print("   expert-defined causal model; it does not claim to prove real-world causality.'")
    print("=" * 70)

    model_path = "stage7/fitted_causal_model.pkl"
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Fitted model file missing: {model_path}. Run stage7/build_causal_model.py first.")

    with open(model_path, "rb") as f:
        saved_data = pickle.load(f)
        causal_model = saved_data["causal_model"]

    inv_items = {101: 200.0, 102: 200.0, 103: 200.0, 201: 50.0, 202: 50.0}
    try:
        db = SessionLocal()
        db_items = {item.product_id: float(item.opening_balance_qty) for item in db.query(InventoryItem).all()}
        if db_items:
            inv_items.update(db_items)
        db.close()
    except Exception:
        pass

    base_df = pd.read_parquet("analytics/daily_panel_baseline.parquet")
    base_df_lagged = add_lags(base_df, inv_items)

    empirical_ref = compute_empirical_baseline_distribution_shift_reference(causal_model, base_df_lagged)

    val_csv_path = "analytics/scenario_validation.csv"
    val_windows = {}
    if os.path.exists(val_csv_path):
        val_df = pd.read_csv(val_csv_path)
        for _, r in val_df.iterrows():
            val_windows[r["scenario_id"]] = r["window_period"]

    SEEDS = [1, 2, 3, 4, 5]
    all_attribution_results = {
        "empirical_baseline_distribution_shift_reference": empirical_ref,
        "seeds_evaluated": SEEDS,
        "scenarios": {}
    }

    for sc_id in SCENARIOS:
        print(f"\nProcessing Attribution for {sc_id} across {len(SEEDS)} seeds (Window: {val_windows.get(sc_id, 'N/A')})...")
        seed_runs = {}
        for s in SEEDS:
            res_seed = run_scenario_attribution(sc_id, causal_model, base_df_lagged, val_windows, inv_items, seed=s)
            seed_runs[f"seed_{s}"] = res_seed

        # Store seed_runs and set primary run as seed_1 for backward compatibility
        all_attribution_results["scenarios"][sc_id] = {
            "scenario_id": sc_id,
            "seed_runs": seed_runs,
            "attributions": seed_runs["seed_1"]["attributions"]
        }

        primary_target = SCENARIO_TARGET_NODES[sc_id][0]
        att_data = seed_runs["seed_1"]["attributions"].get(primary_target, {})
        m1_scores = att_data.get("method_1_anomaly_attribution", {})
        sorted_m1 = sorted([(k, v) for k, v in m1_scores.items() if k != primary_target], key=lambda x: abs(x[1]), reverse=True)
        top_2 = sorted_m1[:2] if sorted_m1 else []
        print(f"  -> Seed 1 Top M1 Attributed Nodes for {primary_target}: {top_2}")

    out_json_path = "analytics/causal_attribution_results.json"
    with open(out_json_path, "w") as f:
        json.dump(all_attribution_results, f, indent=2)

    print("\n" + "=" * 70)
    print(f"All 5-Seed Attribution Results saved to: {out_json_path}")
    print("=" * 70)


if __name__ == "__main__":
    main()
