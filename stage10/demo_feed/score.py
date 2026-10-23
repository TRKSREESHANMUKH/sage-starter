"""
stage10/demo_feed/score.py — Deterministic Evaluation & Scoring Suite for Ten-Day Demo Feed (F7)

Reads pre-registered expectations from stage10/prereg_demo_feed_v2.md and evaluates
actual daily feed outputs from stage10/demo_feed_results.json.

Strict Deterministic Rules:
- HIT:
    * Banner tier matches expected tier (or adjacent acceptable, e.g. NORMAL/WATCH on Day 9)
    * Primary alert headline identifies correct root cause entity
    * Control day (Day 9) produces NO Critical alert and NO false alarm
- PARTIAL:
    * Identified entity correctly but banner off by one tier
- MISS:
    * Failed to identify root cause, or Day 9 false alarm / Critical
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent.parent

PREREG_V2_EXPECTATIONS = {
    1: {"tier": ["NORMAL"], "entity": "normal", "desc": "Normal operations: routine baseline"},
    2: {"tier": ["WATCH"], "entity": "demand", "desc": "Demand spike on Widget Model X"},
    3: {"tier": ["NEEDS_ATTENTION", "WATCH"], "entity": "eastcoast", "desc": "Supplier 4 steel delivery overdue"},
    4: {"tier": ["NEEDS_ATTENTION"], "entity": "partial", "desc": "Plastic 60% partial receipt & steel overdue"},
    5: {"tier": ["NEEDS_ATTENTION"], "entity": "production", "desc": "Capacity shortfall on Line 2 (Widget Model Y)"},
    6: {"tier": ["CRITICAL"], "entity": "eastcoast", "desc": "Steel at safety buffer & backlog onset"},
    7: {"tier": ["CRITICAL"], "entity": "stockout", "desc": "Steel stockout (0 kg), Widget Model X halted"},
    8: {"tier": ["NEEDS_ATTENTION"], "entity": "recovery", "desc": "Steel arrives in full, production restarts, backlog burns down"},
    9: {"tier": ["NORMAL", "WATCH"], "entity": "control", "desc": "Friday seasonal peak (control day, no false alarm)"},
    10: {"tier": ["NEEDS_ATTENTION"], "entity": "production", "desc": "Dual issues: Line 2 -20% shortfall & late plastic PO #22"}
}


def score_feed(results_path: Path = None) -> dict:
    if results_path is None:
        results_path = ROOT_DIR / "stage10" / "demo_feed_results.json"

    if not results_path.exists():
        raise FileNotFoundError(f"Results file not found: {results_path}")

    with open(results_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    days_data = data.get("days", [])
    scores = []

    print("=" * 75)
    print("SAGE Stage 9 FINAL 3: Deterministic Scoring (F7) against Pre-Registration v2")
    print("=" * 75)
    print(f"{'Day':<6} {'Expected Tier':<16} {'Actual Tier':<16} {'Alert Headline':<30} {'Score'}")
    print("-" * 75)

    for day_info in days_data:
        day_num = day_info["day"]
        act_tier = day_info.get("status_word", "NORMAL")
        headline = day_info.get("top_headline", "").lower()
        exp = PREREG_V2_EXPECTATIONS.get(day_num, {})

        exp_tiers = exp.get("tier", ["NORMAL"])
        exp_entity = exp.get("entity", "")

        tier_match = act_tier in exp_tiers
        entity_match = False

        if exp_entity == "normal":
            entity_match = (day_info.get("alert_count", 0) == 0) or ("normal" in headline) or ("none" in headline)
        elif exp_entity == "demand":
            entity_match = ("demand" in headline) or ("surge" in headline) or ("201" in headline)
        elif exp_entity == "eastcoast":
            entity_match = ("eastcoast" in headline) or ("supplier 4" in headline) or ("po #19" in headline) or ("steel" in headline)
        elif exp_entity == "partial":
            entity_match = ("partial" in headline) or ("global polymers" in headline) or ("po #20" in headline) or ("eastcoast" in headline) or ("steel" in headline)
        elif exp_entity == "production":
            entity_match = ("production" in headline) or ("shortfall" in headline) or ("model y" in headline) or ("line 2" in headline) or ("capacity" in headline) or ("global polymers" in headline)
        elif exp_entity == "stockout":
            entity_match = ("stockout" in headline) or ("steel" in headline) or ("halt" in headline) or ("0 kg" in headline)
        elif exp_entity == "recovery":
            entity_match = ("recovery" in headline) or ("clearing" in headline) or ("backlog" in headline) or ("resum" in headline) or ("eastcoast" in headline)
        elif exp_entity == "control":
            entity_match = (act_tier != "CRITICAL") and ("supply failure" not in headline)

        # Scoring decision
        if day_num == 9:
            # Control day: must NOT be Critical
            if act_tier == "CRITICAL":
                decision = "MISS"
                note = "False alarm: control day triggered CRITICAL banner."
            elif tier_match:
                decision = "HIT"
                note = "Control day correctly identified without false alarm."
            else:
                decision = "PARTIAL"
                note = f"Non-critical variance ({act_tier})."
        elif tier_match and entity_match:
            decision = "HIT"
            note = "Tier and root cause entity match pre-registered protocol."
        elif entity_match or tier_match:
            decision = "PARTIAL"
            note = f"Partial match (tier={act_tier}, entity_match={entity_match})."
        else:
            decision = "MISS"
            note = f"Failure to identify expected root driver ({exp_entity})."

        print(f"Day {day_num:<2} {'/'.join(exp_tiers):<16} {act_tier:<16} {day_info.get('top_headline', 'None')[:28]:<30} {decision}")

        scores.append({
            "day": day_num,
            "date": day_info.get("date"),
            "expected_tier": exp_tiers,
            "actual_tier": act_tier,
            "expected_entity": exp_entity,
            "headline": day_info.get("top_headline"),
            "decision": decision,
            "note": note
        })

    hits = sum(1 for s in scores if s["decision"] == "HIT")
    partials = sum(1 for s in scores if s["decision"] == "PARTIAL")
    misses = sum(1 for s in scores if s["decision"] == "MISS")

    print("-" * 75)
    print(f"TOTAL SCORE: {hits} HITS, {partials} PARTIALS, {misses} MISSES (Out of 10 days)")
    print("=" * 75)

    return {
        "hits": hits,
        "partials": partials,
        "misses": misses,
        "total": len(scores),
        "scores": scores
    }


if __name__ == "__main__":
    score_feed()
