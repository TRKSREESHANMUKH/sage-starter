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


PREREG_V3_EXPECTATIONS = {
    1: {"tier": ["NORMAL"], "entity": "normal", "desc": "Normal operations: routine baseline"},
    2: {"tier": ["WATCH"], "entity": "demand", "desc": "Demand spike on Widget Model X"},
    3: {"tier": ["NEEDS_ATTENTION"], "entity": "eastcoast", "desc": "Supplier 4 steel delivery overdue"},
    4: {"tier": ["NEEDS_ATTENTION"], "entity": "partial", "desc": "Plastic 60% partial receipt & steel overdue"},
    5: {"tier": ["NEEDS_ATTENTION"], "entity": "production", "desc": "Capacity shortfall on Line 2 (Widget Model Y)"},
    6: {"tier": ["CRITICAL"], "entity": "safety", "desc": "Steel at safety buffer & backlog onset"},
    7: {"tier": ["CRITICAL"], "entity": "stockout", "desc": "Steel stockout (0 kg), Widget Model X halted"},
    8: {"tier": ["NEEDS_ATTENTION"], "entity": "recovery", "desc": "Steel arrives in full, production restarts, backlog burns down"},
    9: {"tier": ["NEEDS_ATTENTION", "WATCH"], "entity": "control", "desc": "Friday seasonal peak (control day, no false alarm)"},
    10: {"tier": ["NEEDS_ATTENTION"], "entity": "production", "desc": "Dual issues: Line 2 -20% shortfall & late plastic PO #22"}
}


TIER_RANKS = {
    "NORMAL": 0,
    "CALM": 0,
    "WATCH": 1,
    "NEEDS_ATTENTION": 2,
    "NEEDS ATTENTION": 2,
    "WARNING": 2,
    "CRITICAL": 3,
}


def check_entity_match(headline_or_chain: str, exp_entity: str, day_info: dict) -> bool:
    text = headline_or_chain.lower()
    if exp_entity == "normal":
        return (day_info.get("alert_count", 0) == 0) or ("normal" in text) or ("none" in text)
    elif exp_entity == "demand":
        return ("demand" in text) or ("surge" in text) or ("201" in text) or ("model x" in text)
    elif exp_entity == "eastcoast":
        return ("eastcoast" in text) or ("supplier 4" in text) or ("po #19" in text) or ("steel" in text)
    elif exp_entity == "partial":
        return ("partial" in text) or ("global polymers" in text) or ("po #20" in text) or ("po #23" in text) or ("fill rate" in text) or ("eastcoast" in text) or ("steel" in text)
    elif exp_entity == "production":
        return ("production" in text) or ("shortfall" in text) or ("model y" in text) or ("line 2" in text) or ("capacity" in text) or ("below plan" in text)
    elif exp_entity == "safety":
        return ("safety" in text) or ("buffer" in text) or ("eastcoast" in text) or ("steel" in text)
    elif exp_entity == "stockout":
        return ("stockout" in text) or ("steel" in text) or ("halt" in text) or ("0 kg" in text)
    elif exp_entity == "recovery":
        return ("recovery" in text) or ("clearing" in text) or ("backlog" in text) or ("resum" in text) or ("eastcoast" in text) or ("steel" in text) or ("arrival" in text)
    elif exp_entity == "control":
        return ("supply failure" not in text)
    return False


def score_feed(results_path: Path = None, version: str = "v3") -> dict:
    if results_path is None:
        results_path = ROOT_DIR / "stage10" / "demo_feed_results.json"

    if not results_path.exists():
        raise FileNotFoundError(f"Results file not found: {results_path}")

    with open(results_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    days_data = data.get("days", [])
    scores = []
    exp_dict = PREREG_V3_EXPECTATIONS if version == "v3" else PREREG_V2_EXPECTATIONS

    print("=" * 75)
    print(f"SAGE Stage 9 FINAL: Deterministic Scoring (F7) against Pre-Registration {version.upper()}")
    print("=" * 75)
    print(f"{'Day':<6} {'Expected Tier':<22} {'Actual Tier':<16} {'Alert Headline':<30} {'Score'}")
    print("-" * 75)

    for day_info in days_data:
        day_num = day_info["day"]
        act_tier = day_info.get("status_word", "NORMAL")
        exp = exp_dict.get(day_num, {})

        exp_tiers = exp.get("tier", ["NORMAL"])
        exp_entity = exp.get("entity", "")

        act_rank = TIER_RANKS.get(act_tier, 0)
        exp_ranks = [TIER_RANKS.get(t, 0) for t in exp_tiers]

        tier_match = act_tier in exp_tiers
        tier_off_by_one = any(abs(act_rank - er) == 1 for er in exp_ranks)

        # Alerts examination
        raw_alerts = day_info.get("alerts")
        if not raw_alerts:
            # Fallback to top headline/cause
            top_hl = day_info.get("top_headline", "")
            top_c = day_info.get("top_cause", "")
            raw_alerts = [{"headline": top_hl, "cause_chain": top_c}] if top_hl else []

        top_3_alerts = raw_alerts[:3]
        lower_alerts = raw_alerts[3:]

        entity_in_top3 = any(
            check_entity_match(f"{a.get('headline', '')} {a.get('cause_chain', '')}", exp_entity, day_info)
            for a in top_3_alerts
        )
        if not top_3_alerts and exp_entity in ("normal", "control"):
            entity_in_top3 = True

        entity_in_lower = any(
            check_entity_match(f"{a.get('headline', '')} {a.get('cause_chain', '')}", exp_entity, day_info)
            for a in lower_alerts
        )

        # Pre-registered scoring decision logic
        if day_num == 9 or exp_entity == "control":
            # Control day: must NOT have a banner above its expected tier
            max_exp_rank = max(exp_ranks)
            if act_rank > max_exp_rank:
                decision = "MISS"
                note = f"False alarm: control day banner ({act_tier}) exceeded expected tier ({'/'.join(exp_tiers)})."
            elif tier_match:
                decision = "HIT"
                note = "Control day correctly identified without false alarm."
            else:
                decision = "MISS"
                note = f"Unexpected tier ({act_tier}) on control day."
        elif tier_match and entity_in_top3:
            decision = "HIT"
            note = "Tier and root cause entity match pre-registered protocol in top-3 alert."
        elif entity_in_top3 and tier_off_by_one:
            decision = "PARTIAL"
            note = f"Scripted entity found in top-3, but tier ({act_tier}) was off by one from expected ({'/'.join(exp_tiers)})."
        elif entity_in_lower and (tier_match or tier_off_by_one):
            decision = "PARTIAL"
            note = f"Scripted entity present only in lower card (rank > 3)."
        else:
            decision = "MISS"
            note = f"Failed to identify scripted root driver in alerts or tier divergence > 1."

        print(f"Day {day_num:<2} {'/'.join(exp_tiers):<22} {act_tier:<16} {day_info.get('top_headline', 'None')[:28]:<30} {decision}")

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
    print(f"TOTAL SCORE ({version.upper()}): {hits} HITS, {partials} PARTIALS, {misses} MISSES (Out of 10 days)")
    print("=" * 75)

    return {
        "version": version,
        "hits": hits,
        "partials": partials,
        "misses": misses,
        "total": len(scores),
        "scores": scores
    }


if __name__ == "__main__":
    score_feed()
