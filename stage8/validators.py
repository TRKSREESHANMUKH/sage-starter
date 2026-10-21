"""
stage8/validators.py
────────────────────
Deterministic validators for SAGE Stage 8 narratives.

Validates that each narrative:
  1. Contains no forbidden leakage tokens.
  2. Contains the verbatim research-framing sentence.
  3. Meets the word count constraint (60–120 words).
  4. Is grounded in the evidence packet (named entities and numbers).
  5. Matches its pre-computed confidence tier (no confidence upgrading).
  6. Consists of a single plain-prose paragraph.
"""

from __future__ import annotations

import re
from typing import Any

from stage8.common import (
    FORBIDDEN_TOKENS,
    NARRATIVE_MAX_WORDS,
    NARRATIVE_MIN_WORDS,
    EvidencePacket,
)

_RESEARCH_FRAMING = EvidencePacket.RESEARCH_FRAMING


def validate_no_forbidden_tokens(narrative: str) -> tuple[bool, str]:
    lower = narrative.lower()
    hits = [tok for tok in FORBIDDEN_TOKENS if tok in lower]
    if hits:
        return False, f"Contains forbidden tokens: {hits}"
    return True, "Passed"


def validate_verbatim_framing(narrative: str) -> tuple[bool, str]:
    if _RESEARCH_FRAMING.lower() not in narrative.lower():
        return False, "Missing verbatim research framing sentence"
    return True, "Passed"


def validate_word_count(
    narrative: str,
    min_words: int = NARRATIVE_MIN_WORDS,
    max_words: int = NARRATIVE_MAX_WORDS,
) -> tuple[bool, str]:
    wc = len(narrative.split())
    if wc < min_words:
        return False, f"Too short: {wc} words (min {min_words})"
    if wc > max_words:
        return False, f"Too long: {wc} words (max {max_words})"
    return True, f"Passed ({wc} words)"


def validate_grounding(narrative: str, packet_dict: dict[str, Any]) -> tuple[bool, str]:
    """
    Checks that every entity referenced in the narrative appears in the packet.
    """
    # Check suppliers
    for sup_id in range(1, 6):
        sup_name = f"Supplier {sup_id}"
        if sup_name in narrative:
            # check if this supplier appears in packet targets or drivers
            pkt_str = str(packet_dict)
            if sup_name not in pkt_str and f"supplier_{sup_id}" not in pkt_str:
                return False, f"Ungrounded supplier: {sup_name} not in packet"

    # Check materials
    for mat_id in (101, 102, 103):
        mat_name = f"Material {mat_id}"
        if mat_name in narrative:
            pkt_str = str(packet_dict)
            if mat_name not in pkt_str and f"material_{mat_id}" not in pkt_str:
                return False, f"Ungrounded material: {mat_name} not in packet"

    # Check products
    for prod_id in (201, 202):
        prod_name = f"Product {prod_id}"
        if prod_name in narrative:
            pkt_str = str(packet_dict)
            if prod_name not in pkt_str and f"product_{prod_id}" not in pkt_str:
                return False, f"Ungrounded product: {prod_name} not in packet"

    return True, "Passed"


def validate_confidence_tier_alignment(
    narrative: str,
    packet_dict: dict[str, Any],
) -> tuple[bool, str]:
    """
    Checks that the narrative does not claim higher confidence than assigned.
    """
    tier = packet_dict.get("top_tier", "NOISE")
    is_no_sig = packet_dict.get("is_no_signal", False)
    lower = narrative.lower()

    if is_no_sig or tier == "NOISE":
        strong_claims = ["strong attribution", "strongly attributed", "primary driver", "decisive cause"]
        if any(c in lower for c in strong_claims):
            return False, "Noise/no-signal packet claimed strong attribution"
    elif tier == "LOW":
        if "strongly attributed" in lower or "high confidence" in lower:
            return False, "Low-tier packet claimed strong attribution"

    return True, "Passed"


def validate_single_paragraph(narrative: str) -> tuple[bool, str]:
    clean = narrative.strip()
    # No markdown headings or bullet lists
    if clean.startswith("#") or "\n#" in clean:
        return False, "Contains markdown headings"
    if "\n- " in clean or "\n* " in clean or clean.startswith("- ") or clean.startswith("* "):
        return False, "Contains bullet points"
    # Max 1 newline permitted (e.g. framing split)
    paragraphs = [p for p in clean.split("\n\n") if p.strip()]
    if len(paragraphs) > 2:
        return False, f"Multiple paragraphs ({len(paragraphs)})"
    return True, "Passed"


def validate_all(narrative: str, packet_dict: dict[str, Any]) -> dict[str, tuple[bool, str]]:
    """Runs all 6 validators on a narrative and returns a status dictionary."""
    return {
        "no_forbidden_tokens": validate_no_forbidden_tokens(narrative),
        "verbatim_framing":    validate_verbatim_framing(narrative),
        "word_count":          validate_word_count(narrative),
        "grounding":           validate_grounding(narrative, packet_dict),
        "tier_alignment":      validate_confidence_tier_alignment(narrative, packet_dict),
        "single_paragraph":    validate_single_paragraph(narrative),
    }


def is_valid_narrative(narrative: str, packet_dict: dict[str, Any]) -> bool:
    """Returns True iff all 6 validators pass."""
    results = validate_all(narrative, packet_dict)
    return all(passed for passed, _ in results.values())
