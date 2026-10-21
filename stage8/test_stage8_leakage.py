"""
stage8/test_stage8_leakage.py
──────────────────────────────
Security audit and integrity test suite for Stage 8.

Verifies:
  1. AST scan: stage8/*.py (excluding common.py and evaluation scripts) contains
     no forbidden ground-truth tokens or filenames.
  2. Runtime open guard: assert_path_allowed blocks ground-truth paths and event tables.
  3. Packet determinism: building packets twice produces identical byte serialization.
  4. Prompt validation: prompts contain no forbidden tokens and use anonymous IDs.
  5. Narrative validation: narratives pass all 6 deterministic validators.
  6. Tier determinism: score_to_tier produces identical results across calls.
  7. Frozen guard: Stage 8 prerequisite check halts if stage7/FROZEN.json is absent.
  8. Mutation test: a temporary mutant script attempting leakage is blocked.
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

STAGE8_DIR   = Path(__file__).resolve().parent
PROJECT_ROOT = STAGE8_DIR.parent


def _pass(msg: str) -> None:
    print(f"  ✓  {msg}")

def _fail(msg: str) -> None:
    print(f"  ✗  FAIL: {msg}", file=sys.stderr)


# ──────────────────────────────────────────────────────────────────────────────
# Test 1: AST scan
# ──────────────────────────────────────────────────────────────────────────────
_FORBIDDEN_STRINGS = [
    "scenario_causal_evaluation",
    "business_events",
    "incident_type",
    "ground_truth",
]

def test_ast_scan() -> bool:
    print("\n[1] AST scan of stage8/*.py ...")
    ok = True
    for py_file in sorted(STAGE8_DIR.glob("*.py")):
        # Skip common.py (which defines the guard lists) and evaluation/test files
        if py_file.name in ("common.py", "evaluate_narratives.py") or py_file.name.startswith("test_"):
            continue

        src = py_file.read_text()
        try:
            tree = ast.parse(src)
        except SyntaxError as e:
            _fail(f"{py_file.name}: SyntaxError – {e}")
            ok = False
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                for tok in _FORBIDDEN_STRINGS:
                    if tok in node.value:
                        _fail(f"{py_file.name}: forbidden string '{tok}' found in code/constant")
                        ok = False

    if ok:
        _pass("No forbidden strings found in operational Stage 8 files")
    return ok


# ──────────────────────────────────────────────────────────────────────────────
# Test 2: Runtime open guard
# ──────────────────────────────────────────────────────────────────────────────
def test_runtime_open_guard() -> bool:
    print("\n[2] Runtime open guard ...")
    from stage8.common import assert_path_allowed, FORBIDDEN_PATHS
    ok = True
    for path in sorted(FORBIDDEN_PATHS):
        try:
            assert_path_allowed(path)
            _fail(f"assert_path_allowed did NOT raise for {path}")
            ok = False
        except RuntimeError:
            _pass(f"Correctly blocked: {Path(path).name}")
    return ok


# ──────────────────────────────────────────────────────────────────────────────
# Test 3: Packet determinism
# ──────────────────────────────────────────────────────────────────────────────
def test_packet_determinism() -> bool:
    print("\n[3] Packet determinism check ...")
    from stage8.build_evidence_packets import build_all_packets, verify_packet_determinism
    try:
        pkts = build_all_packets()
        _pass(f"Built {len(pkts)} packets without error")
        det = verify_packet_determinism()
        if det:
            _pass("Packet determinism confirmed: identical byte-for-byte serialization across builds")
        else:
            _fail("Packet determinism failed: multiple builds produced differing bytes")
        return det
    except Exception as e:
        _fail(f"Packet build failed: {e}")
        traceback.print_exc()
        return False


# ──────────────────────────────────────────────────────────────────────────────
# Test 4: Prompt validation
# ──────────────────────────────────────────────────────────────────────────────
def test_prompt_validation() -> bool:
    print("\n[4] Prompt validation ...")
    from stage8.build_evidence_packets import build_all_packets
    from stage8.build_prompts import build_prompt_pair
    from stage8.common import validate_prompt
    try:
        packets = build_all_packets()
        ok = True
        for pkt_id, pkt in packets.items():
            sys_p, usr_p = build_prompt_pair(pkt)
            try:
                validate_prompt(sys_p)
                validate_prompt(usr_p)
                assert pkt.packet_id.startswith("P"), f"Packet ID {pkt.packet_id} should be anonymous"
                assert "INC_" not in usr_p, f"Internal scenario ID leaked into user prompt for {pkt_id}"
            except Exception as e:
                _fail(f"{pkt_id}: {e}")
                ok = False
        if ok:
            _pass("All prompts passed forbidden-token check and use anonymous packet IDs")
        return ok
    except Exception as e:
        _fail(f"Prompt test failed: {e}")
        traceback.print_exc()
        return False


# ──────────────────────────────────────────────────────────────────────────────
# Test 5: Narrative validation
# ──────────────────────────────────────────────────────────────────────────────
def test_narrative_validation() -> bool:
    print("\n[5] Narrative validation ...")
    from stage8.build_evidence_packets import build_all_packets
    from stage8.ollama_client import generate_fallback_narrative
    from stage8.validators import is_valid_narrative, validate_all

    try:
        packets = build_all_packets()
        ok = True
        for pkt_id, pkt in packets.items():
            narrative = generate_fallback_narrative(pkt.to_dict())
            val_results = validate_all(narrative, pkt.to_dict())
            all_passed = is_valid_narrative(narrative, pkt.to_dict())
            if not all_passed:
                _fail(f"{pkt_id}: failed validation: {val_results}")
                ok = False
        if ok:
            _pass(f"All {len(packets)} narratives passed all 6 deterministic validators")
        return ok
    except Exception as e:
        _fail(f"Narrative validation failed: {e}")
        traceback.print_exc()
        return False


# ──────────────────────────────────────────────────────────────────────────────
# Test 6: Tier determinism
# ──────────────────────────────────────────────────────────────────────────────
def test_tier_determinism() -> bool:
    print("\n[6] Confidence tier determinism ...")
    from stage8.common import score_to_tier, TIER_HIGH, TIER_MEDIUM, TIER_LOW, TIER_NOISE
    cases = [
        (0.50, 1.20, TIER_HIGH),
        (0.25, 0.95, TIER_HIGH),
        (0.25, 0.40, TIER_MEDIUM),
        (0.10, 0.10, TIER_LOW),
        (0.01, 0.01, TIER_NOISE),
    ]
    ok = True
    for m1, m2, expected in cases:
        got = score_to_tier(m1, m2)
        if got != expected:
            _fail(f"score_to_tier({m1}, {m2}) = {got}, expected {expected}")
            ok = False
    if ok:
        _pass(f"All {len(cases)} confidence tier cases matched expectations")
    return ok


# ──────────────────────────────────────────────────────────────────────────────
# Test 7: FROZEN.json prerequisite guard
# ──────────────────────────────────────────────────────────────────────────────
def test_frozen_guard() -> bool:
    print("\n[7] FROZEN.json prerequisite guard ...")
    from stage8.common import check_frozen, FROZEN_PATH
    backup = FROZEN_PATH.with_suffix(".json.testbak")
    try:
        if FROZEN_PATH.exists():
            FROZEN_PATH.rename(backup)
        try:
            check_frozen()
            _fail("check_frozen() did not raise when FROZEN.json is absent")
            return False
        except RuntimeError:
            _pass("RuntimeError correctly raised when FROZEN.json is missing")
        return True
    finally:
        if backup.exists():
            backup.rename(FROZEN_PATH)


# ──────────────────────────────────────────────────────────────────────────────
# Test 8: Mutation test
# ──────────────────────────────────────────────────────────────────────────────
def test_mutation_test() -> bool:
    print("\n[8] Mutation test (leakage interception on temporary script) ...")
    # Write a mutant script in a temp directory that tries to access forbidden ground-truth file
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tf:
        tf.write(
            "import sys\n"
            "from pathlib import Path\n"
            "sys.path.insert(0, '" + str(PROJECT_ROOT) + "')\n"
            "from stage8.common import assert_path_allowed, ANALYTICS_DIR\n"
            "forbidden = ANALYTICS_DIR / 'scenario_causal_evaluation.json'\n"
            "try:\n"
            "    assert_path_allowed(forbidden)\n"
            "    print('LEAKAGE_VULNERABILITY')\n"
            "except RuntimeError as e:\n"
            "    print('MUTANT_BLOCKED:', e)\n"
        )
        temp_script = tf.name

    try:
        res = subprocess.run(
            [sys.executable, temp_script],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        output = res.stdout.strip()
        if "MUTANT_BLOCKED:" in output:
            _pass(f"Mutant attempt successfully intercepted: {output}")
            return True
        else:
            _fail(f"Mutant attempt was NOT intercepted! Output: {output}")
            return False
    finally:
        if os.path.exists(temp_script):
            os.remove(temp_script)


# ──────────────────────────────────────────────────────────────────────────────
# Runner
# ──────────────────────────────────────────────────────────────────────────────
def main() -> None:
    print("=" * 65)
    print("SAGE Stage 8 – Security, Leakage & Integrity Audit")
    print("=" * 65)

    tests = [
        test_ast_scan,
        test_runtime_open_guard,
        test_packet_determinism,
        test_prompt_validation,
        test_narrative_validation,
        test_tier_determinism,
        test_frozen_guard,
        test_mutation_test,
    ]

    results = []
    for test_fn in tests:
        try:
            passed = test_fn()
        except Exception as exc:
            _fail(f"Unexpected exception in {test_fn.__name__}: {exc}")
            traceback.print_exc()
            passed = False
        results.append((test_fn.__name__, passed))

    print("\n" + "=" * 65)
    print("Audit Summary")
    print("=" * 65)
    n_pass = sum(1 for _, p in results if p)
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {status:<6} {name}")

    print(f"\nResult: {n_pass}/{len(results)} tests passed.")
    if n_pass != len(results):
        sys.exit(1)
    print("All checks passed – Stage 8 leakage audit CLEAN.")


if __name__ == "__main__":
    main()
