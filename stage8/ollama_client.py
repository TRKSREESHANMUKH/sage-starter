"""
stage8/ollama_client.py
────────────────────────
Client for the narration LLM with executive-grade deterministic fallback.

Responsibilities:
  • POST to Ollama /api/chat when available.
  • Validate generated narratives against stage8/validators.py.
  • When Ollama is offline or unavailable, provide the deterministic
    grounded fallback generator written specifically for Plant Managers,
    Operations Supervisors, and Executives.
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from typing import Any, Optional

from stage8.common import (
    OLLAMA_HOST,
    OLLAMA_MAX_RETRIES,
    OLLAMA_MODEL,
    OLLAMA_TIMEOUT_SECONDS,
    EvidencePacket,
)
from stage8.validators import is_valid_narrative, validate_all

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# 1.  Low-level HTTP call to Ollama
# ──────────────────────────────────────────────────────────────────────────────
def _post_chat(
    system_prompt: str,
    user_prompt: str,
    model: str = OLLAMA_MODEL,
    timeout: int = OLLAMA_TIMEOUT_SECONDS,
) -> str:
    url = f"{OLLAMA_HOST.rstrip('/')}/api/chat"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        "stream": False,
        "options": {
            "temperature": 0.2,
            "top_p": 0.9,
            "num_predict": 256,
        },
    }
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode()

    result = json.loads(raw)
    return result["message"]["content"].strip()


# ──────────────────────────────────────────────────────────────────────────────
# 2.  Executive-grade deterministic fallback generator
# ──────────────────────────────────────────────────────────────────────────────
def generate_fallback_narrative(packet_dict: dict[str, Any]) -> str:
    """
    Executive-grade fallback narrative generator designed for Managers and CEOs.
    Guaranteed to:
      - Contain only entities and drivers present in the packet.
      - Meet 60–120 word count bounds.
      - Align with the assigned confidence tier.
      - Avoid technical algorithm notation (M1/M2 scores).
      - Include actionable operational guidance.
      - Conclude with the verbatim research framing.
    """
    top_tier  = packet_dict.get("top_tier", "NOISE")
    is_no_sig = packet_dict.get("is_no_signal", False)
    drivers   = packet_dict.get("drivers", [])
    targets   = packet_dict.get("target_labels", packet_dict.get("target_nodes", []))
    target_str = ", ".join(targets[:2]) if targets else "monitored production lines"
    framing   = EvidencePacket.RESEARCH_FRAMING

    # 1. Normal operations / no disruption detected
    if is_no_sig or top_tier == "NOISE" or not drivers:
        return (
            f"Operational Status for {target_str}: All manufacturing, inventory, and "
            "fulfillment metrics operated within normal baseline tolerances throughout the "
            "monitored window. The causal evaluation detected no anomalous supply disruptions "
            "or production bottlenecks requiring floor intervention. Routine manufacturing "
            "schedules and standard inventory replenishment workflows should proceed as planned "
            f"without operational adjustments. {framing}"
        )

    top_d   = drivers[0]
    d_node  = top_d.get("node", "")
    d_label = top_d.get("label", "operational driver")
    d_tier  = top_d.get("tier", top_tier)

    tier_desc = "high" if d_tier == "HIGH" else ("moderate" if d_tier == "MEDIUM" else "low")

    # 2. Demand-driven disruption
    if "demand" in d_node:
        return (
            f"Operations Briefing for {target_str}: Elevated customer demand outpaced planned "
            "plant throughput during the monitored window, resulting in due backlog and depleted "
            f"finished goods buffers. The causal evaluation attributes the observed schedule strain "
            f"primarily to {d_label} with {tier_desc} confidence. Production supervisors should "
            "evaluate short-term overtime or shift reallocations to restore inventory buffers and "
            f"prevent shipment delays. {framing}"
        )

    # 3. Internal capacity / production bottleneck
    if "capacity" in d_node or "production" in d_node:
        return (
            f"Operations Briefing for {target_str}: Internal workcenter throughput constraints "
            "created a production shortfall during the monitored window. The causal evaluation "
            f"confirms with {tier_desc} confidence that the primary operational bottleneck was "
            f"{d_label}. Plant supervisors should review equipment availability and line staffing "
            "to resolve throughput limitations before increasing master production order schedules. "
            f"{framing}"
        )

    # 4. Supplier delivery or material receipt delay
    if "po_delay" in d_node or "receipt" in d_node or "supplier" in d_node:
        if d_tier == "LOW":
            return (
                f"Supply Chain Advisory for {target_str}: Moderate inventory cover fluctuations "
                "were detected during the monitored window, with preliminary attribution signals "
                f"pointing toward {d_label}. However, the causal evaluation classifies this with low "
                "confidence, indicating the disruption was largely absorbed by safety stock buffers. "
                "Procurement teams should track upcoming delivery schedules without initiating disruptive "
                f"floor rescheduling. {framing}"
            )
        return (
            f"Supply Chain Alert for {target_str}: Upstream delivery timing created significant "
            "inventory cover pressure across the monitored window. The causal evaluation identified "
            f"{d_label} as the primary operational driver with {tier_desc} confidence. Procurement "
            "supervisors should coordinate with supplier representatives to expedite pending purchase "
            f"orders and review safety stock replenishment triggers to prevent stockouts. {framing}"
        )

    # 5. Seasonal / calendar variation
    if "month" in d_node or "weekday" in d_node:
        return (
            f"Planning Briefing for {target_str}: Operating volumes reflected predictable calendar "
            f"patterns rather than unexpected equipment or supplier failures. The causal evaluation "
            f"confirmed with {tier_desc} confidence that observed throughput aligned with {d_label}. "
            "Operations and sales teams should maintain standard seasonal inventory policies without "
            f"emergency floor intervention. {framing}"
        )

    # Generic fallback
    return (
        f"Operations Briefing for {target_str}: The causal model identified operational signals "
        f"attributed to {d_label} with {tier_desc} confidence across the monitored window. Plant "
        "supervisors should review workcenter performance and raw material covers to ensure planned "
        f"production targets remain on schedule. {framing}"
    )


# ──────────────────────────────────────────────────────────────────────────────
# 3.  Public generation function
# ──────────────────────────────────────────────────────────────────────────────
def generate_narrative(
    packet: EvidencePacket,
    system_prompt: str,
    user_prompt: str,
) -> tuple[str, str, int, dict[str, tuple[bool, str]]]:
    pkt_dict = packet.to_dict()
    is_stub  = os.getenv("SAGE_OLLAMA_STUB", "").lower() in ("1", "true", "yes")

    if is_stub:
        narrative = generate_fallback_narrative(pkt_dict)
        val_res = validate_all(narrative, pkt_dict)
        return narrative, "fallback", 1, val_res

    attempts = 0
    last_val_res: dict[str, tuple[bool, str]] = {}

    for attempt in range(1, OLLAMA_MAX_RETRIES + 1):
        attempts = attempt
        try:
            raw_text = _post_chat(system_prompt, user_prompt)
            val_res = validate_all(raw_text, pkt_dict)
            last_val_res = val_res

            if all(passed for passed, _ in val_res.values()):
                logger.info("Ollama generated valid narrative for %s on attempt %d", packet.packet_id, attempt)
                return raw_text, "ollama", attempt, val_res
            else:
                logger.warning("Ollama narrative for %s failed validation (attempt %d): %s", packet.packet_id, attempt, val_res)

        except (urllib.error.URLError, OSError, TimeoutError) as net_err:
            logger.info("Ollama service unavailable (%s); using executive fallback narrator.", net_err)
            break
        except Exception as exc:
            logger.warning("Ollama call failed (attempt %d): %s", attempt, exc)

    logger.info("Engaging executive fallback narrator for %s", packet.packet_id)
    fallback_text = generate_fallback_narrative(pkt_dict)
    val_res = validate_all(fallback_text, pkt_dict)
    return fallback_text, "fallback", attempts if attempts > 0 else 1, val_res
