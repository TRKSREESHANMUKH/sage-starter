"""
stage9/status.py — Operational Status & Mechanical Calibration Evaluators.

Strict Rule:
- Display status for buffer absorption must be computed exclusively from panel facts,
  never from scenario labels or business_events.
- Calibration labels are mechanically derived from rule predicates, never hardcoded.
- P10 is mechanically identified as 'False positive on negative control'.
"""

from typing import Dict, Any, List

RESEARCH_FRAMING = (
    "SAGE performs controlled synthetic causal-attribution evaluation under an "
    "expert-defined causal model; it does not claim to prove real-world causality."
)


def compute_daily_status_and_actions(as_of, db_session=None, source=None):
    from stage9.ops import compute_daily_status_and_actions as _impl
    return _impl(as_of, db_session=db_session, source=source)


def compute_buffer_absorption_status(
    po_delays_observed: List[float],
    min_stock_observed: float,
    safety_stock: float
) -> bool:
    """
    Evaluates whether a delay was observed but cleanly absorbed by safety stock:
    Rule:
      1. A supplier PO delay > 0 days was observed in the window, AND
      2. The dependent material stock stayed strictly above safety_stock throughout.
    """
    has_delay = any(d > 0.0 for d in po_delays_observed)
    buffer_held = min_stock_observed > safety_stock
    return bool(has_delay and buffer_held)


EVIDENCE_LABELS = {
    "HIGH": "Strong evidence",
    "MEDIUM": "Some evidence",
    "LOW": "Weak evidence",
    "NOISE": "Nothing unusual",
}


def tier_to_evidence_label(tier: str) -> str:
    """Converts a tier string to plain evidence wording."""
    return EVIDENCE_LABELS.get(str(tier).upper(), "Nothing unusual")


def get_packet_display_status(packet: Dict[str, Any]) -> str:
    """
    Computes plain human-facing display status for an evidence record.
    HIGH -> Strong evidence
    MEDIUM -> Some evidence
    LOW -> Weak evidence
    NOISE -> Nothing unusual
    """
    if packet.get("buffer_held", False):
        return "Delay observed, buffer held"
    tier = str(packet.get("top_tier", "NOISE")).upper()
    return EVIDENCE_LABELS.get(tier, "Nothing unusual")


def compute_mechanical_calibration_label(
    category: str,
    top_tier: str,
    driver_matches: bool,
    is_control: bool
) -> Dict[str, str]:
    """
    Computes the calibration status using an audited, mechanical rule.
    Returns:
      {
        "status": label string,
        "is_honest_pass": bool,
        "rule_applied": exact mechanical formula description
      }
    """
    # 1. Negative control / Seasonal control check
    if is_control or category in ("negative_control", "normal_variation", "seasonal_control"):
        if top_tier in ("HIGH", "MEDIUM"):
            return {
                "status": "False positive on negative control",
                "is_honest_pass": False,
                "rule_applied": "IF is_control AND tier in (HIGH, MEDIUM) -> False positive"
            }
        else:
            return {
                "status": "True negative (Correct rejection)",
                "is_honest_pass": True,
                "rule_applied": "IF is_control AND tier in (LOW, NOISE) -> Correct rejection"
            }

    # 2. Real incident evaluation
    if driver_matches:
        if top_tier in ("HIGH", "MEDIUM"):
            return {
                "status": f"Calibrated detection ({top_tier})",
                "is_honest_pass": True,
                "rule_applied": "IF driver_matches AND tier in (HIGH, MEDIUM) -> Calibrated detection"
            }
        elif top_tier == "LOW":
            return {
                "status": "Tempered signal (Low confidence)",
                "is_honest_pass": True,
                "rule_applied": "IF driver_matches AND tier == LOW -> Tempered signal"
            }
        else:
            return {
                "status": "Signal diluted (Averaging/exogenous filter)",
                "is_honest_pass": False,
                "rule_applied": "IF driver_matches AND tier == NOISE -> Signal diluted by multi-target averaging"
            }
    else:
        # Driver mismatched
        if top_tier == "NOISE":
            return {
                "status": "Signal diluted / Unattributed",
                "is_honest_pass": False,
                "rule_applied": "IF not driver_matches AND tier == NOISE -> Below null threshold"
            }
        else:
            return {
                "status": "Misattributed driver",
                "is_honest_pass": False,
                "rule_applied": "IF not driver_matches AND tier != NOISE -> Divergent root cause"
            }
