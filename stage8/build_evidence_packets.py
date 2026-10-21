"""
stage8/build_evidence_packets.py
─────────────────────────────────
Reads analytics/causal_attribution_results.json (Stage 7 output) and
produces one EvidencePacket per scenario.

Security and isolation:
  • Does not read any ground-truth source or evaluation label files.
  • The packet given to the LLM uses an anonymous identifier (e.g. P01..P10);
    no scenario identifiers or incident types are passed to the prompt.
  • Filters candidate causes to exogenous root drivers (is_exogenous_node).
  • Confidence tiers are computed deterministically via common.score_to_tier().
  • The ranked driver list is the ONLY information the LLM will receive.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from stage8.common import (
    ATTRIBUTION_PATH,
    ANALYTICS_DIR,
    MAX_NAMED_DRIVERS,
    SCENARIO_TO_PACKET,
    DriverEntry,
    EvidencePacket,
    assert_path_allowed,
    check_frozen,
    is_exogenous_node,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# 1.  Aggregate scores across seeds and targets
# ──────────────────────────────────────────────────────────────────────────────
def _aggregate_scores(
    seed_runs: dict[str, dict],
    target_nodes: list[str],
) -> dict[str, dict[str, float]]:
    """
    Pool M1 and M2 absolute scores across all seeds and target nodes for exogenous drivers.
    Returns: {node: {"m1": <mean |M1|>, "m2": <mean |M2|>}}
    """
    node_m1: dict[str, list[float]] = {}
    node_m2: dict[str, list[float]] = {}

    for seed_key, seed_data in seed_runs.items():
        attributions: dict[str, Any] = seed_data.get("attributions", {})
        for target in target_nodes:
            target_attr = attributions.get(target, {})
            m1_dict = target_attr.get("method_1_anomaly_attribution", {})
            m2_dict = target_attr.get("method_2_distribution_change_attribution", {})

            all_nodes = set(m1_dict) | set(m2_dict)
            for node in all_nodes:
                if not is_exogenous_node(node):
                    continue
                node_m1.setdefault(node, []).append(abs(m1_dict.get(node, 0.0)))
                node_m2.setdefault(node, []).append(abs(m2_dict.get(node, 0.0)))

    result: dict[str, dict[str, float]] = {}
    all_nodes = set(node_m1) | set(node_m2)
    for node in sorted(all_nodes):
        m1_vals = node_m1.get(node, [0.0])
        m2_vals = node_m2.get(node, [0.0])
        result[node] = {
            "m1": sum(m1_vals) / len(m1_vals),
            "m2": sum(m2_vals) / len(m2_vals),
        }

    return result


# ──────────────────────────────────────────────────────────────────────────────
# 2.  Rank drivers
# ──────────────────────────────────────────────────────────────────────────────
def _rank_drivers(
    agg_scores: dict[str, dict[str, float]],
    top_n: int = MAX_NAMED_DRIVERS,
) -> list[DriverEntry]:
    """
    Sort nodes by combined signal strength (m1 + m2), assign tiers,
    and return only the top-N DriverEntry objects.
    Ties broken deterministically by node name.
    """
    ranked = sorted(
        agg_scores.items(),
        key=lambda kv: (kv[1]["m1"] + kv[1]["m2"], kv[0]),
        reverse=True,
    )

    entries: list[DriverEntry] = []
    for rank, (node, scores) in enumerate(ranked[:top_n], start=1):
        entry = DriverEntry(
            node=node,
            m1_score=scores["m1"],
            m2_score=scores["m2"],
            rank=rank,
        )
        entries.append(entry)

    return entries


# ──────────────────────────────────────────────────────────────────────────────
# 3.  Extract window period, targets, and seeds
# ──────────────────────────────────────────────────────────────────────────────
def _extract_window(seed_runs: dict[str, dict]) -> str:
    for seed_data in seed_runs.values():
        w = seed_data.get("window_period", "unknown")
        if w:
            return str(w)
    return "unknown"

def _extract_targets(seed_runs: dict[str, dict]) -> list[str]:
    for seed_data in seed_runs.values():
        t = seed_data.get("target_nodes", [])
        if t:
            return sorted(list(t))
    return []

def _extract_seeds(seed_runs: dict[str, dict]) -> list[int]:
    seeds = []
    for seed_data in seed_runs.values():
        s = seed_data.get("seed")
        if s is not None:
            seeds.append(int(s))
    return sorted(seeds)


# ──────────────────────────────────────────────────────────────────────────────
# 4.  Public: build one packet
# ──────────────────────────────────────────────────────────────────────────────
def build_packet(scenario_id: str, scenario_data: dict[str, Any]) -> EvidencePacket:
    packet_id = SCENARIO_TO_PACKET.get(scenario_id, scenario_id)
    seed_runs: dict[str, dict] = scenario_data.get("seed_runs", {})

    window_period = _extract_window(seed_runs)
    target_nodes  = _extract_targets(seed_runs)
    seeds_used    = _extract_seeds(seed_runs)

    if not seed_runs:
        return EvidencePacket(
            packet_id=packet_id,
            scenario_id=scenario_id,
            window_period=window_period,
            target_nodes=target_nodes,
            drivers=[],
            seeds_used=seeds_used,
        )

    agg_scores = _aggregate_scores(seed_runs, target_nodes)
    drivers    = _rank_drivers(agg_scores, top_n=MAX_NAMED_DRIVERS)

    return EvidencePacket(
        packet_id=packet_id,
        scenario_id=scenario_id,
        window_period=window_period,
        target_nodes=target_nodes,
        drivers=drivers,
        seeds_used=seeds_used,
    )


# ──────────────────────────────────────────────────────────────────────────────
# 5.  Public: build all packets
# ──────────────────────────────────────────────────────────────────────────────
def build_all_packets() -> dict[str, EvidencePacket]:
    check_frozen()
    assert_path_allowed(ATTRIBUTION_PATH)

    with ATTRIBUTION_PATH.open() as fh:
        data = json.load(fh)

    scenarios: dict[str, Any] = data.get("scenarios", {})
    if not scenarios:
        raise ValueError("causal_attribution_results.json contains no scenarios.")

    packets: dict[str, EvidencePacket] = {}
    for sc_id in sorted(scenarios):
        packet = build_packet(sc_id, scenarios[sc_id])
        packets[packet.packet_id] = packet

    return packets


# ──────────────────────────────────────────────────────────────────────────────
# 6.  Serialise / deserialise
# ──────────────────────────────────────────────────────────────────────────────
def save_packets(packets: dict[str, EvidencePacket], out_path: Path | str) -> None:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {pkt_id: pkt.to_dict() for pkt_id, pkt in sorted(packets.items())}
    with out_path.open("w") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)


def load_packets(path: Path | str) -> dict[str, dict]:
    path = Path(path)
    assert_path_allowed(path)
    with path.open() as fh:
        return json.load(fh)


def verify_packet_determinism() -> bool:
    p1 = build_all_packets()
    j1 = json.dumps({k: v.to_dict() for k, v in sorted(p1.items())}, indent=2, sort_keys=True)
    p2 = build_all_packets()
    j2 = json.dumps({k: v.to_dict() for k, v in sorted(p2.items())}, indent=2, sort_keys=True)
    return j1 == j2


if __name__ == "__main__":
    import sys
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ANALYTICS_DIR / "evidence_packets.json"
    pkts = build_all_packets()
    save_packets(pkts, out)
    det = verify_packet_determinism()
    print(f"Packets built: {len(pkts)} | Determinism verified: {det}")
