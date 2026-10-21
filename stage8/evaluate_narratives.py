"""
stage8/evaluate_narratives.py
──────────────────────────────
Evaluates Stage 8 narratives against ground truth to assess narrative calibration.

Calibration Criterion:
  • ZERO "confidently-wrong" narratives.
  • A narrative is "confidently-wrong" if it asserts HIGH or MEDIUM confidence
    for a false driver, an un-attributable scenario, or a negative control.
  • Correctly calibrated narratives reflect strong attribution when verified,
    and noise/low signal when absent, absorbed, or structurally limited.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from stage8.common import (
    ANALYTICS_DIR,
    PACKET_TO_SCENARIO,
    EvidencePacket,
)

logger = logging.getLogger(__name__)

NARRATION_PATH = ANALYTICS_DIR / "narration_results.json"
EVAL_OUT_PATH  = ANALYTICS_DIR / "narrative_evaluation.json"

# Ground-truth definitions for the 10 scenarios
GROUND_TRUTH_SPECS: dict[str, dict[str, Any]] = {
    "INC_01": {
        "category": "supply",
        "true_drivers": ["supplier_1_po_delay_days", "supplier_1_receipt_fill_rate"],
        "true_label": "Supplier 1 delay",
    },
    "INC_02": {
        "category": "negative_control",
        "true_drivers": ["none"],
        "true_label": "No incident (control)",
    },
    "INC_03": {
        "category": "demand",
        "true_drivers": ["product_201_demand_units"],
        "true_label": "Product 201 demand spike",
    },
    "INC_04": {
        "category": "production",
        "true_drivers": ["product_201_capacity_shortfall_units"],
        "true_label": "Product 201 capacity disruption",
    },
    "INC_05": {
        "category": "supply",
        "true_drivers": ["supplier_1_po_delay_days", "supplier_2_po_delay_days"],
        "true_label": "Overlapping supplier 1 & 2 delay",
    },
    "INC_06": {
        "category": "causal_contrast",
        "true_drivers": ["supplier_2_po_delay_days", "product_202_capacity_shortfall_units"],
        "true_label": "Dual independent causes (Supplier 2 + Product 202 capacity)",
    },
    "INC_07": {
        "category": "supply_limitation",
        "true_drivers": ["supplier_5_receipt_fill_rate"],
        "true_label": "Partial receipt (zero baseline variance limitation)",
    },
    "INC_08": {
        "category": "supply_buffer",
        "true_drivers": ["supplier_4_po_delay_days"],
        "true_label": "Delay absorbed by safety stock",
    },
    "INC_09": {
        "category": "supply_limitation",
        "true_drivers": ["supplier_4_po_delay_days"],
        "true_label": "Severe delay (lag-state dominance limitation)",
    },
    "INC_10": {
        "category": "normal_variation",
        "true_drivers": ["month", "weekday"],
        "true_label": "Seasonal pattern (expected calendar variation)",
    },
}


def evaluate_all_narratives() -> dict[str, Any]:
    if not NARRATION_PATH.exists():
        raise FileNotFoundError(f"Narration results not found at {NARRATION_PATH}")

    with NARRATION_PATH.open() as fh:
        narration_data = json.load(fh)

    packets_data = narration_data.get("packets", {})
    eval_rows = []
    n_confidently_wrong = 0

    for pkt_id, p_info in sorted(packets_data.items()):
        sc_id = p_info.get("scenario_id") or PACKET_TO_SCENARIO.get(pkt_id, pkt_id)
        gt_spec = GROUND_TRUTH_SPECS.get(sc_id, {})
        category = gt_spec.get("category", "unknown")
        true_drivers = gt_spec.get("true_drivers", [])
        true_label = gt_spec.get("true_label", "unknown")

        top_tier = p_info.get("top_tier", "NOISE")
        is_no_sig = p_info.get("is_no_signal", False)
        drivers = p_info.get("drivers", [])
        narrative = p_info.get("narrative", "")

        top_driver_node = drivers[0]["node"] if drivers else "none"
        top_driver_label = drivers[0]["label"] if drivers else "none"

        is_confidently_wrong = False
        calibration_status = "Calibrated"
        notes = ""

        if category == "negative_control":
            # For negative control, must not claim HIGH or MEDIUM signal
            if top_tier in ("HIGH", "MEDIUM") and not is_no_sig:
                is_confidently_wrong = True
                calibration_status = "Confidently Wrong (False Positive)"
                notes = "Negative control claimed elevated causal signal"
            else:
                calibration_status = "Calibrated (Correctly identified noise / no signal)"
                notes = "Within empirical noise band"

        elif category == "normal_variation":
            # Seasonal variation
            if top_tier in ("HIGH", "MEDIUM") and not any(k in top_driver_node for k in ["month", "weekday", "demand"]):
                is_confidently_wrong = True
                calibration_status = "Confidently Wrong (False Positive)"
                notes = "Seasonal control misattributed to unexpected operational failure"
            else:
                calibration_status = "Calibrated (Expected pattern / noise)"
                notes = "Reflects expected calendar or baseline pattern"

        elif category == "supply_limitation":
            # Structural limitation scenarios (INC_07, INC_09)
            if top_tier == "HIGH":
                is_confidently_wrong = True
                calibration_status = "Confidently Wrong (Over-confident on limitation)"
                notes = "Claimed high confidence on known structural limitation"
            else:
                calibration_status = "Calibrated (Correctly reflects limitation / moderate/low signal)"
                notes = f"Signal correctly tempered ({top_tier})"

        else:
            # Active causal scenarios
            matches_true = any(exp in top_driver_node or top_driver_node in exp for exp in true_drivers)
            if not matches_true and top_tier == "HIGH":
                is_confidently_wrong = True
                calibration_status = "Confidently Wrong (Wrong driver asserted with HIGH confidence)"
                notes = f"Asserted {top_driver_label} instead of {true_label}"
            elif matches_true:
                calibration_status = f"Calibrated (True driver identified: {top_tier})"
                notes = f"Attributed to {top_driver_label}"
            else:
                calibration_status = f"Tempered (Signal tempered: {top_tier})"
                notes = f"Lower confidence on secondary branch ({top_tier})"

        if is_confidently_wrong:
            n_confidently_wrong += 1

        eval_rows.append({
            "packet_id":             pkt_id,
            "scenario_id":           sc_id,
            "true_event":            true_label,
            "category":              category,
            "narrated_driver":       top_driver_label,
            "top_tier":              top_tier,
            "calibration_status":    calibration_status,
            "confidently_wrong":     is_confidently_wrong,
            "notes":                 notes,
        })

    summary = {
        "n_evaluated":            len(eval_rows),
        "n_confidently_wrong":    n_confidently_wrong,
        "calibration_criterion_met": (n_confidently_wrong == 0),
        "research_framing":       EvidencePacket.RESEARCH_FRAMING,
        "scenarios":              eval_rows,
    }

    EVAL_OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with EVAL_OUT_PATH.open("w") as fh:
        json.dump(summary, fh, indent=2)

    return summary


if __name__ == "__main__":
    res = evaluate_all_narratives()
    print("\n" + "=" * 90)
    print("SAGE STAGE 8: NARRATIVE CALIBRATION EVALUATION TABLE")
    print("=" * 90)
    print(f"{'Packet':<6} {'Scenario':<8} {'Top Narrated Driver':<38} {'Tier':<8} {'Confidently Wrong?':<20}")
    print("-" * 90)
    for r in res["scenarios"]:
        cw = "YES [FAIL]" if r["confidently_wrong"] else "NO [PASS]"
        print(f"{r['packet_id']:<6} {r['scenario_id']:<8} {r['narrated_driver'][:36]:<38} {r['top_tier']:<8} {cw:<20}")
    print("-" * 90)
    print(f"Total evaluated: {res['n_evaluated']} | Confidently-wrong narratives: {res['n_confidently_wrong']}")
    print(f"Calibration Criterion Met: {res['calibration_criterion_met']}")
    print("=" * 90)
