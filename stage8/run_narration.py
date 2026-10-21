"""
stage8/run_narration.py
────────────────────────
Orchestrates the SAGE Stage 8 narration pipeline:
  1. Verifies Stage 7 FROZEN.json prerequisite.
  2. Builds 10 ground-truth-free evidence packets (P01..P10).
  3. Verifies packet determinism (byte-for-byte check).
  4. Generates and validates narratives for each packet.
  5. Records validator status, attempt count, and fallback usage.
  6. Writes analytics/narration_results.json.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from stage8.build_evidence_packets import (
    build_all_packets,
    save_packets,
    verify_packet_determinism,
)
from stage8.build_prompts import build_prompt_pair
from stage8.common import (
    ANALYTICS_DIR,
    EvidencePacket,
    check_frozen,
)
from stage8.ollama_client import generate_narrative
from stage8.validators import is_valid_narrative

logger = logging.getLogger(__name__)

PACKETS_PATH   = ANALYTICS_DIR / "evidence_packets.json"
NARRATION_PATH = ANALYTICS_DIR / "narration_results.json"


def run_narration() -> dict:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )

    logger.info("=" * 65)
    logger.info("SAGE Stage 8 – Ollama Narration Layer")
    logger.info("=" * 65)

    # 1. Prerequisite check
    frozen = check_frozen()
    logger.info("Stage 7 verified frozen (fitted model: %.12s...)", frozen.get("fitted_causal_model_sha256"))

    # 2. Build packets
    packets = build_all_packets()
    save_packets(packets, PACKETS_PATH)
    logger.info("Saved %d packets to %s", len(packets), PACKETS_PATH)

    # 3. Verify determinism
    is_det = verify_packet_determinism()
    logger.info("Packet determinism verified: %s", is_det)
    if not is_det:
        raise RuntimeError("Packet determinism check failed!")

    # 4. Generate narratives
    results: dict[str, dict] = {}
    first_attempt_success = 0
    total_valid = 0

    for pkt_id in sorted(packets):
        packet = packets[pkt_id]
        sys_p, usr_p = build_prompt_pair(packet)

        t0 = time.perf_counter()
        narrative, source, attempts, val_res = generate_narrative(packet, sys_p, usr_p)
        elapsed = round(time.perf_counter() - t0, 3)

        passed_all = all(p for p, _ in val_res.values())
        if passed_all:
            total_valid += 1
            if attempts == 1:
                first_attempt_success += 1

        results[pkt_id] = {
            "packet_id":       packet.packet_id,
            "scenario_id":     packet.scenario_id,
            "window_period":   packet.window_period,
            "target_nodes":    packet.target_nodes,
            "target_labels":   packet.target_labels,
            "top_tier":        packet.top_tier,
            "is_no_signal":    packet.is_no_signal,
            "seeds_used":      packet.seeds_used,
            "drivers":         [d.to_dict() for d in packet.drivers],
            "narrative":       narrative,
            "source":          source,
            "attempts":        attempts,
            "elapsed_s":       elapsed,
            "validators":      {k: {"pass": v[0], "msg": v[1]} for k, v in val_res.items()},
            "is_valid":        passed_all,
        }

    output = {
        "generated_at":           datetime.now(timezone.utc).isoformat(),
        "stage":                  8,
        "fitted_causal_model":    frozen.get("fitted_causal_model_sha256", ""),
        "n_packets":              len(packets),
        "total_valid":            total_valid,
        "first_attempt_rate":     first_attempt_success / len(packets) if packets else 0.0,
        "final_validation_rate":  total_valid / len(packets) if packets else 0.0,
        "packet_determinism":     is_det,
        "research_framing":       EvidencePacket.RESEARCH_FRAMING,
        "packets":                results,
    }

    NARRATION_PATH.parent.mkdir(parents=True, exist_ok=True)
    with NARRATION_PATH.open("w") as fh:
        json.dump(output, fh, indent=2)

    logger.info("Saved narration results to %s", NARRATION_PATH)
    return output


if __name__ == "__main__":
    res = run_narration()
    print("\n--- VALIDATION SUMMARY ---")
    print(f"Total Packets         : {res['n_packets']}")
    print(f"First-attempt Pass Rate: {res['first_attempt_rate']:.1%}")
    print(f"Final Pass Rate       : {res['final_validation_rate']:.1%}")
    print(f"Packet Determinism    : {res['packet_determinism']}")
