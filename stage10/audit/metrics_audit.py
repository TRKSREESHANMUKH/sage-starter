"""
stage10/audit/metrics_audit.py — Stage 7 Causal Benchmark Cohorts Audit
Reads strictly from stage10/audit/truth.json (generated from main PostgreSQL & evaluation artifacts).
NO HARDCODED NUMBERS OR STATIC METRICS.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
TRUTH_PATH = ROOT_DIR / "stage10" / "audit" / "truth.json"


def run_audit():
    if not TRUTH_PATH.exists():
        from stage10.audit.truth import main as generate_truth
        generate_truth()

    with open(TRUTH_PATH, "r", encoding="utf-8") as f:
        truth = json.load(f)

    print("=" * 95)
    print("STAGE 7 CAUSAL BENCHMARK METRICS EVALUATION (metrics_audit.py)")
    print(f"Source: analytics/scenario_causal_evaluation.json via truth.json")
    print("=" * 95)

    scenarios = truth.get("stage7_scenarios", [])
    print(f"\nALL {len(scenarios)} SCENARIOS IN FROZEN EVALUATION SET:")
    header = f"{'INC ID':<8} | {'Classification':<34} | {'True Sources':<32} | {'Rank':<6} | {'Hit@1':<6} | {'Hit@3':<6} | {'RR':<6}"
    print(header)
    print("-" * len(header))

    for s in scenarios:
        sid = s.get("scenario_id", "")
        cls = s.get("classification", "")
        ts = s.get("true_sources", "")
        rk = s.get("avg_rank", 99.0)
        h1 = 1 if rk == 1.0 else 0
        h3 = 1 if rk <= 3.0 else 0
        rr = (1.0 / rk) if rk < 99.0 else 0.0
        print(f"{sid:<8} | {cls[:34]:<34} | {ts[:32]:<32} | {rk:<6.1f} | {h1:<6} | {h3:<6} | {rr:<6.4f}")

    print("-" * len(header))

    print("\nBENCHMARK COHORT BREAKDOWN (CALCULATED DYNAMICALLY):")
    cohorts = truth.get("stage7_cohorts", {})
    for key, c in cohorts.items():
        print(f"\nCOHORT: {c['label']} (N = {c['n']})")
        print(f"  * Included Scenarios : {c.get('ids', [])}")
        print(f"  * Hit@1 (AC@1)       : {c['hit_at_1']}%")
        print(f"  * Hit@3 (AC@3)       : {c['hit_at_3']}%")
        print(f"  * MRR                : {c['mrr']:.4f}")
        print(f"  * Cohort Rationale   : {c['reason']}")

    print("\n" + "=" * 95)


if __name__ == "__main__":
    run_audit()
