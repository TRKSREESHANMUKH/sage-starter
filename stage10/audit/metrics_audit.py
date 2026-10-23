"""
stage10/audit/metrics_audit.py — Stage 7 Causal Benchmark Cohort Analysis
"""

import csv
from pathlib import Path
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
CSV_PATH = ROOT_DIR / "analytics" / "scenario_causal_evaluation.csv"

def evaluate_metrics():
    print("=" * 80)
    print("STAGE 7 CAUSAL BENCHMARK METRICS EVALUATION (scenario_causal_evaluation.csv)")
    print("=" * 80)

    rows = []
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            r["exog_rank"] = float(r["exogenous_rank"]) if r["exogenous_rank"] != "N/A" else 99.0
            rows.append(r)

    print(f"\nALL 10 SCENARIO ROWS EVALUATED:")
    print(f"{'INC ID':<8} | {'Category / Notes':<32} | {'True Driver':<32} | {'Rank':<6} | {'Hit@1':<6} | {'Hit@3':<6} | {'RR':<6}")
    print("-" * 105)

    for r in rows:
        rk = r["exog_rank"]
        h1 = 1 if rk == 1.0 else 0
        h3 = 1 if rk <= 3.0 else 0
        rr = (1.0 / rk) if rk < 99.0 else 0.0
        print(f"{r['scenario_id']:<8} | {r['classification'][:32]:<32} | {r['true_driver(s)_from_DB'][:32]:<32} | {rk:<6.1f} | {h1:<6} | {h3:<6} | {rr:<6.4f}")

    print("-" * 105)

    # 4 Cohorts:
    # 1. All 10
    # 2. Excluding INC_01 and INC_05 (8 cases)
    # 3. Stage 7 primary real-cause cohort (6 cases: excluding INC_02, 10, 07, 09)
    # 4. Valid real-cause cohort (4 cases: excluding INC_01 and INC_05 from the 6)

    def calc_cohort(cohort_rows, name):
        n = len(cohort_rows)
        h1 = sum(1 for r in cohort_rows if r["exog_rank"] == 1.0)
        h3 = sum(1 for r in cohort_rows if r["exog_rank"] <= 3.0)
        rrs = [1.0 / r["exog_rank"] if r["exog_rank"] < 99 else 0.0 for r in cohort_rows]
        mrr = float(np.mean(rrs)) if rrs else 0.0
        print(f"\nCOHORT: {name} (N = {n})")
        print(f"  * Hit@1 (AC@1) : {h1}/{n} ({h1/n*100.0:.1f}%)")
        print(f"  * Hit@3 (AC@3) : {h3}/{n} ({h3/n*100.0:.1f}%)")
        print(f"  * MRR          : {mrr:.4f}")
        return h1, h3, mrr

    calc_cohort(rows, "1. All 10 Evaluation Scenarios")
    c8 = [r for r in rows if r["scenario_id"] not in ["INC_01", "INC_05"]]
    calc_cohort(c8, "2. Excluding Sourcing Bug (8 Scenarios)")
    c6 = [r for r in rows if r["scenario_id"] in ["INC_01", "INC_03", "INC_04", "INC_05", "INC_06", "INC_08"]]
    calc_cohort(c6, "3. Stage 7 Evaluated Real-Cause Cohort (6 Scenarios)")
    c4 = [r for r in rows if r["scenario_id"] in ["INC_03", "INC_04", "INC_06", "INC_08"]]
    calc_cohort(c4, "4. Valid Non-Bugged Real-Cause Cohort (4 Scenarios)")

    print("\nCOHORT INCLUSION / EXCLUSION RATIONALE:")
    print("  * INC_01: IN 10, IN 6. OUT of 8 and 4 (Sourcing bug: Supplier 1 received 0 orders).")
    print("  * INC_02: IN 10, IN 8. OUT of 6 and 4 (Negative control: no incident injected).")
    print("  * INC_03: IN all 4 cohorts (Demand surge on Product 201).")
    print("  * INC_04: IN all 4 cohorts (Capacity shortfall on Line 1).")
    print("  * INC_05: IN 10, IN 6. OUT of 8 and 4 (Sourcing bug: Suppliers 1 & 2 received 0 orders).")
    print("  * INC_06: IN all 4 cohorts (Compound capacity + supplier disruption).")
    print("  * INC_07: IN 10, IN 8. OUT of 6 and 4 (Structural limitation: zero baseline fill rate variance).")
    print("  * INC_08: IN all 4 cohorts (Safety stock buffer absorption on Material 103).")
    print("  * INC_09: IN 10, IN 8. OUT of 6 and 4 (Structural limitation: lag-state persistence suppresses exog rank).")
    print("  * INC_10: IN 10, IN 8. OUT of 6 and 4 (Seasonal control: Friday demand calendar pattern).")
    print("  NOTE: Sample size n is small across all cohorts (4 to 10 scenarios); figures must be interpreted as controlled benchmarks.")
    print("=" * 80)

if __name__ == "__main__":
    evaluate_metrics()
