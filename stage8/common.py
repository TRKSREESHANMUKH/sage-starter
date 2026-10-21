"""
stage8/common.py
────────────────
Shared constants, data structures, and helper utilities for the SAGE
narration layer (Stage 8).

Hard rules (enforced here, not just stated):
  1. No read of ground-truth tables or evaluation result files.
     FORBIDDEN_PATHS enforces this at load-time.
  2. Confidence tiers are deterministic functions of raw scores – the LLM
     cannot influence them.
  3. FORBIDDEN_TOKENS prevents label leakage into prompts.
  4. Every number the LLM can name must originate in the evidence packet.

Research framing (must appear verbatim in every outbound report):
  SAGE performs controlled synthetic causal-attribution evaluation under an
  expert-defined causal model; it does not claim to prove real-world causality.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

# ──────────────────────────────────────────────────────────────────────────────
# 0.  Root paths
# ──────────────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
STAGE7_DIR   = PROJECT_ROOT / "stage7"
ANALYTICS_DIR = PROJECT_ROOT / "analytics"

FROZEN_PATH      = STAGE7_DIR / "FROZEN.json"
ATTRIBUTION_PATH = ANALYTICS_DIR / "causal_attribution_results.json"
PANEL_PATH       = ANALYTICS_DIR / "daily_panel_baseline.parquet"

# ──────────────────────────────────────────────────────────────────────────────
# 1.  Files that Stage 8 must NEVER open  (leakage trap)
# ──────────────────────────────────────────────────────────────────────────────
FORBIDDEN_PATHS: set[str] = {
    str(ANALYTICS_DIR / "scenario_causal_evaluation.json"),
    str(ANALYTICS_DIR / "scenario_causal_evaluation.csv"),
    str(ANALYTICS_DIR / "run_manifest.json"),
}

# Also flag any caller that tries to read these prefixes
FORBIDDEN_PREFIXES: tuple[str, ...] = (
    "business_events",
    "incident_type",
    "ground_truth",
)

def assert_path_allowed(path: str | Path) -> None:
    """Raise RuntimeError if the caller is attempting to open a forbidden file."""
    p = str(Path(path).resolve())
    if p in FORBIDDEN_PATHS:
        raise RuntimeError(
            f"[LEAKAGE GUARD] Stage 8 must not open ground-truth file: {p}"
        )
    basename = Path(p).stem.lower()
    for prefix in FORBIDDEN_PREFIXES:
        if prefix in basename:
            raise RuntimeError(
                f"[LEAKAGE GUARD] Stage 8 must not open file containing '{prefix}': {p}"
            )


# ──────────────────────────────────────────────────────────────────────────────
# 2.  Forbidden tokens – must not appear in any LLM prompt or output
# ──────────────────────────────────────────────────────────────────────────────
FORBIDDEN_TOKENS: set[str] = {
    # ground-truth incident labels
    "incident_type",
    "ground_truth",
    "true_cause",
    "actual_cause",
    "scenario_causal_evaluation",
    "scenario_manifest",
    "negative_control",
    "supplier_delay",
    "demand_spike",
    "capacity_disruption",
    "partial_receipt",
    "delay_absorbed_by_safety_stock",
    "severe_supplier_delay_stockout",
    "two_simultaneous_independent_causes",
    "overlapping_supplier_delay",
    "seasonal_demand",
    "no_incident",
    # DB columns with ground-truth meaning
    "business_events",
    "incident_id",
    "is_anomaly_period",
    "causal_chain",
}

def validate_prompt(prompt: str) -> None:
    """Raise ValueError if any forbidden token appears in the prompt."""
    lower = prompt.lower()
    hits = [tok for tok in FORBIDDEN_TOKENS if tok in lower]
    if hits:
        raise ValueError(
            f"[LEAKAGE GUARD] Prompt contains forbidden tokens: {hits}"
        )

def validate_narrative(text: str) -> None:
    """Raise ValueError if any forbidden token appears in the LLM output."""
    lower = text.lower()
    hits = [tok for tok in FORBIDDEN_TOKENS if tok in lower]
    if hits:
        raise ValueError(
            f"[LEAKAGE GUARD] Narrative contains forbidden tokens: {hits}"
        )


# ──────────────────────────────────────────────────────────────────────────────
# 3.  Exogenous node filter & Confidence tier thresholds
# ──────────────────────────────────────────────────────────────────────────────
def is_exogenous_node(node: str) -> bool:
    """
    Checks if a node is an exogenous driver candidate (root cause).
    Matches Stage 7 pre-registered attribution specification.
    """
    if str(node).endswith("_lag1"):
        return False
    exog_patterns = [
        "po_delay_days", "receipt_fill_rate", "capacity_shortfall_units",
        "demand_units", "weekday", "month"
    ]
    return any(p in node for p in exog_patterns)


TIER_HIGH   = "HIGH"
TIER_MEDIUM = "MEDIUM"
TIER_LOW    = "LOW"
TIER_NOISE  = "NOISE"

# Empirical null thresholds from stage7/FROZEN.json
M1_NULL_THRESHOLD = 0.218006
M2_NULL_THRESHOLD = 0.922611

def score_to_tier(m1_abs: float, m2_abs: float) -> str:
    """
    Deterministic mapping from (|M1|, |M2|) -> confidence tier
    based on Stage 7 pre-registered empirical null thresholds.
    """
    if m1_abs >= M1_NULL_THRESHOLD and m2_abs >= M2_NULL_THRESHOLD:
        return TIER_HIGH
    if m1_abs >= M1_NULL_THRESHOLD:
        return TIER_MEDIUM
    if m1_abs >= 0.10:
        return TIER_LOW
    return TIER_NOISE


# ──────────────────────────────────────────────────────────────────────────────
# 4.  Master data lookup
# ──────────────────────────────────────────────────────────────────────────────
SUPPLIER_LABELS: dict[str, str] = {
    "supplier_1": "Supplier 1",
    "supplier_2": "Supplier 2",
    "supplier_3": "Supplier 3",
    "supplier_4": "Supplier 4",
    "supplier_5": "Supplier 5",
}

MATERIAL_LABELS: dict[str, str] = {
    "material_101": "Material 101",
    "material_102": "Material 102",
    "material_103": "Material 103",
}

PRODUCT_LABELS: dict[str, str] = {
    "product_201": "Product 201",
    "product_202": "Product 202",
}

METRIC_DESCRIPTIONS: dict[str, str] = {
    "po_delay_days":            "purchase-order delay (days)",
    "receipt_fill_rate":        "receipt fill-rate (fraction of PO received)",
    "receipt_event_flag":       "receipt event flag",
    "stock":                    "stock level (units)",
    "days_of_cover":            "days of cover",
    "open_po_flag":             "open purchase-order flag",
    "reorder_triggered":        "reorder-trigger flag",
    "fg_stock":                 "finished-goods stock (units)",
    "planned_production":       "planned production (units)",
    "actual_production":        "actual production (units)",
    "production_shortfall":     "production shortfall (units)",
    "capacity_shortfall_units":  "capacity shortfall (units)",
    "demand_units":             "demand (units)",
    "due_backlog_units":        "due-backlog (units)",
    "newly_backordered_units":  "newly back-ordered units",
    "backorder_flag":           "back-order flag",
}

def node_to_label(node: str) -> str:
    lag_suffix = ""
    name = node
    if name.endswith("_lag1"):
        lag_suffix = " [lag-1]"
        name = name[:-5]

    for key, label in SUPPLIER_LABELS.items():
        if name.startswith(key + "_"):
            metric_key = name[len(key) + 1:]
            metric = METRIC_DESCRIPTIONS.get(metric_key, metric_key.replace("_", " "))
            return f"{label} – {metric}{lag_suffix}"

    for key, label in MATERIAL_LABELS.items():
        if name.startswith(key + "_"):
            metric_key = name[len(key) + 1:]
            metric = METRIC_DESCRIPTIONS.get(metric_key, metric_key.replace("_", " "))
            return f"{label} – {metric}{lag_suffix}"

    for key, label in PRODUCT_LABELS.items():
        if name.startswith(key + "_"):
            metric_key = name[len(key) + 1:]
            metric = METRIC_DESCRIPTIONS.get(metric_key, metric_key.replace("_", " "))
            return f"{label} – {metric}{lag_suffix}"

    generic = {
        "weekday": "day-of-week",
        "month":   "calendar month",
        "is_weekend": "weekend flag",
    }
    if name in generic:
        return generic[name] + lag_suffix

    return node.replace("_", " ") + lag_suffix

def target_to_label(target: str) -> str:
    return node_to_label(target)


# ──────────────────────────────────────────────────────────────────────────────
# 5.  Evidence packet schema with anonymous packet IDs (P01..P10)
# ──────────────────────────────────────────────────────────────────────────────
SCENARIO_TO_PACKET: dict[str, str] = {f"INC_{i:02d}": f"P{i:02d}" for i in range(1, 11)}
PACKET_TO_SCENARIO: dict[str, str] = {f"P{i:02d}": f"INC_{i:02d}" for i in range(1, 11)}

class DriverEntry:
    __slots__ = ("node", "label", "m1_score", "m2_score", "tier", "rank")

    def __init__(self, node: str, m1_score: float, m2_score: float, rank: int) -> None:
        self.node     = node
        self.label    = node_to_label(node)
        self.m1_score = round(m1_score, 6)
        self.m2_score = round(m2_score, 6)
        self.tier     = score_to_tier(abs(m1_score), abs(m2_score))
        self.rank     = rank

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank":     self.rank,
            "node":     self.node,
            "label":    self.label,
            "m1_score": self.m1_score,
            "m2_score": self.m2_score,
            "tier":     self.tier,
        }

class EvidencePacket:
    __slots__ = (
        "packet_id",
        "scenario_id",
        "window_period",
        "target_nodes",
        "target_labels",
        "drivers",
        "top_tier",
        "is_no_signal",
        "seeds_used",
        "research_framing",
    )

    RESEARCH_FRAMING = (
        "SAGE performs controlled synthetic causal-attribution evaluation under "
        "an expert-defined causal model; it does not claim to prove real-world causality."
    )

    def __init__(
        self,
        packet_id: str,
        scenario_id: str,
        window_period: str,
        target_nodes: list[str],
        drivers: list[DriverEntry],
        seeds_used: list[int],
    ) -> None:
        self.packet_id       = packet_id
        self.scenario_id     = scenario_id
        self.window_period   = window_period
        self.target_nodes    = target_nodes
        self.target_labels   = [target_to_label(t) for t in target_nodes]
        self.drivers         = drivers
        self.seeds_used      = seeds_used
        self.research_framing = self.RESEARCH_FRAMING

        top3_tiers = [d.tier for d in drivers[:3]] if drivers else []
        tier_order = {TIER_HIGH: 3, TIER_MEDIUM: 2, TIER_LOW: 1, TIER_NOISE: 0}
        self.top_tier     = max(top3_tiers, key=lambda t: tier_order[t]) if top3_tiers else TIER_NOISE
        self.is_no_signal = (self.top_tier == TIER_NOISE)

    def to_dict(self) -> dict[str, Any]:
        return {
            "packet_id":       self.packet_id,
            "scenario_id":     self.scenario_id,
            "window_period":   self.window_period,
            "target_nodes":    self.target_nodes,
            "target_labels":   self.target_labels,
            "top_tier":        self.top_tier,
            "is_no_signal":    self.is_no_signal,
            "seeds_used":      self.seeds_used,
            "drivers":         [d.to_dict() for d in self.drivers],
            "research_framing": self.research_framing,
        }

    def to_prompt_dict(self) -> dict[str, Any]:
        d = self.to_dict()
        d.pop("scenario_id", None)
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


# ──────────────────────────────────────────────────────────────────────────────
# 6.  FROZEN.json prerequisite check
# ──────────────────────────────────────────────────────────────────────────────
def check_frozen() -> dict:
    if not FROZEN_PATH.exists():
        raise RuntimeError(
            f"stage7/FROZEN.json not found at {FROZEN_PATH}. "
            "Run Stage 7 to completion before starting Stage 8."
        )
    with FROZEN_PATH.open() as fh:
        frozen = json.load(fh)
    return frozen


# ──────────────────────────────────────────────────────────────────────────────
# 7.  Narrative constants
# ──────────────────────────────────────────────────────────────────────────────
MAX_NAMED_DRIVERS = 3
NARRATIVE_MIN_WORDS = 60
NARRATIVE_MAX_WORDS = 120

OLLAMA_MODEL = os.getenv("SAGE_OLLAMA_MODEL", "gemma3:4b")
OLLAMA_HOST  = os.getenv("SAGE_OLLAMA_HOST",  "http://localhost:11434")
OLLAMA_TIMEOUT_SECONDS = int(os.getenv("SAGE_OLLAMA_TIMEOUT", "60"))
OLLAMA_MAX_RETRIES = int(os.getenv("SAGE_OLLAMA_RETRIES", "3"))
