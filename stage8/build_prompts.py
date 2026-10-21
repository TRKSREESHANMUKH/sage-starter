"""
stage8/build_prompts.py
────────────────────────
Converts an EvidencePacket into an executive-level prompt pair
(system_prompt, user_prompt) for the narration model.

Tailored for Operations Supervisors, Plant Managers, and Executives:
  • Eliminates algorithm jargon (M1, M2, seeds) from the primary narrative.
  • Translates causal findings into business impact and operational guidance.
  • Strictly preserves grounding: only names entities and drivers in the packet.
  • Concludes with the verbatim research framing.
"""

from __future__ import annotations

from stage8.common import (
    MAX_NAMED_DRIVERS,
    NARRATIVE_MAX_WORDS,
    NARRATIVE_MIN_WORDS,
    TIER_HIGH,
    TIER_MEDIUM,
    TIER_LOW,
    TIER_NOISE,
    EvidencePacket,
    validate_prompt,
)

# ──────────────────────────────────────────────────────────────────────────────
# 1.  System prompt
# ──────────────────────────────────────────────────────────────────────────────
_SYSTEM_PROMPT = f"""You are the SAGE Operations Briefing Narrator. Your role is \
to brief Plant Supervisors, Supply Chain Managers, and Executives on causal \
findings in plain business language without technical algorithm jargon.

HARD RULES you must obey on every response:
1. You are a NARRATOR, not an analyst. Every cause you cite must appear explicitly \
in the provided evidence drivers list.
2. Name AT MOST {MAX_NAMED_DRIVERS} drivers using their exact operational name.
3. Write between {NARRATIVE_MIN_WORDS} and {NARRATIVE_MAX_WORDS} words in a single \
clear prose paragraph. No bullet points, headers, or markdown.
4. Do not include raw algorithm formulas or mathematical score notation like M1 or M2. \
Instead, convey confidence in plain English (high confidence, moderate confidence, or baseline noise).
5. State the operational impact, the primary driver, and whether floor intervention is warranted.
6. Always end with the verbatim sentence:
   "SAGE performs controlled synthetic causal-attribution evaluation under an \
expert-defined causal model; it does not claim to prove real-world causality."
7. If all drivers are in the NOISE tier, explain that operations operated within normal \
baseline limits with no significant disruption detected and no intervention required."""

_TIER_PHRASES: dict[str, str] = {
    TIER_HIGH:   "high confidence",
    TIER_MEDIUM: "moderate confidence",
    TIER_LOW:    "low confidence / exploratory",
    TIER_NOISE:  "baseline variability (no disruption)",
}


# ──────────────────────────────────────────────────────────────────────────────
# 2.  Build user prompt from packet
# ──────────────────────────────────────────────────────────────────────────────
def build_user_prompt(packet: EvidencePacket) -> str:
    """Builds an executive prompt turn using anonymous packet_id only."""
    lines: list[str] = []

    lines.append(f"Operations Packet: {packet.packet_id}")
    lines.append(f"Monitored Window : {packet.window_period}")
    lines.append("Monitored Line(s): " + ", ".join(packet.target_labels))
    lines.append(f"Confidence Level : {packet.top_tier} ({_TIER_PHRASES.get(packet.top_tier, packet.top_tier)})")
    lines.append("")

    if packet.is_no_signal:
        lines.append(
            "Evidence Summary: All operational metrics remained strictly within "
            "normal baseline tolerances. No abnormal disruptions or bottlenecks occurred."
        )
        lines.append("")
        lines.append(
            "Instruction: Write a concise manager update stating that operations ran "
            "normally within baseline parameters and no intervention is required. "
            "End with the required research framing sentence."
        )
        prompt = "\n".join(lines)
        validate_prompt(prompt)
        return prompt

    lines.append(f"Attributed Operational Drivers (Top {len(packet.drivers)}):")
    for d in packet.drivers:
        tier_desc = _TIER_PHRASES.get(d.tier, d.tier)
        lines.append(f"  • Rank {d.rank}: {d.label} (Confidence: {tier_desc})")
    lines.append("")

    lines.append(
        "Instruction: Write a clear executive paragraph explaining what occurred, "
        "identifying the primary driver and affected line, indicating whether "
        "operational action is needed, and stating the confidence level in plain terms. "
        "Do not include technical algorithm scores (M1/M2). End with the required research framing sentence."
    )

    prompt = "\n".join(lines)
    validate_prompt(prompt)
    return prompt


# ──────────────────────────────────────────────────────────────────────────────
# 3.  Public factory
# ──────────────────────────────────────────────────────────────────────────────
def build_prompt_pair(packet: EvidencePacket) -> tuple[str, str]:
    validate_prompt(_SYSTEM_PROMPT)
    user = build_user_prompt(packet)
    return _SYSTEM_PROMPT, user
