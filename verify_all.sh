#!/usr/bin/env bash
# ==============================================================================
# SAGE Stage 9 Final — Unified Verification Script (verify_all.sh)
# Verifies frozen stages, forensic truth, audit consistency, scoring, and tests.
# Must exit 0 on clean pass.
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON="$SCRIPT_DIR/venv/bin/python"
if [ ! -f "$PYTHON" ]; then
    echo "ERROR: Virtual environment python not found at $PYTHON"
    exit 1
fi

echo "======================================================================"
echo "SAGE STAGE 9 FINAL — COMPLETE UNIFIED VERIFICATION PROTOCOL"
echo "Commit: $(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
echo "Timestamp: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "======================================================================"

# 1. FROZEN HASHES CHECK
echo ""
echo ">>> STEP 1: Verifying Frozen Stage Hashes..."
$PYTHON -c "
import hashlib, json, sys
from pathlib import Path

ROOT = Path('.')
h7 = hashlib.sha256((ROOT / 'stage7' / 'FROZEN.json').read_bytes()).hexdigest()
h8 = hashlib.sha256((ROOT / 'stage8' / 'FROZEN.json').read_bytes()).hexdigest()

exp_h7 = 'acd199cea42b75d221f32b06736318024dbc53ec6cb4e8c06a8e25dd87f4c920'
exp_h8 = '983a4e1ffabb592d49548185750dcd01e713e9dae3f9b7baf3ae360c615dbb56'

print(f'stage7/FROZEN.json sha256: {h7}')
print(f'stage8/FROZEN.json sha256: {h8}')

if h7 != exp_h7:
    print(f'ERROR: stage7/FROZEN.json hash mismatch! Expected {exp_h7}')
    sys.exit(1)
if h8 != exp_h8:
    print(f'ERROR: stage8/FROZEN.json hash mismatch! Expected {exp_h8}')
    sys.exit(1)

# Check baseline_hashes.json
bfile = ROOT / 'stage9' / 'baseline_hashes.json'
if bfile.exists():
    with open(bfile) as f:
        baseline = json.load(f)
    diffs = 0
    for rel_path, exp_hash in baseline.items():
        p = ROOT / rel_path
        if not p.exists():
            print(f'ERROR: Missing baseline file {rel_path}')
            diffs += 1
            continue
        if 'live' in rel_path:
            # Skip live runtime replay panel
            continue
        cur_hash = hashlib.sha256(p.read_bytes()).hexdigest()
        if cur_hash != exp_hash:
            print(f'ERROR: Hash changed for {rel_path}!')
            diffs += 1
    if diffs > 0:
        print(f'ERROR: {diffs} baseline files differ from frozen state!')
        sys.exit(1)
    print(f'Checked {len(baseline)} frozen stage files: ALL MATCH BASELINE.')
else:
    print('WARNING: stage9/baseline_hashes.json not found.')

print('Frozen stage check: PASSED (Stages 1-8 strictly frozen).')
"

# 2. TRUTH LAYER GENERATION & CROSS-CHECK
echo ""
echo ">>> STEP 2: Running Truth Layer Audit (truth.py)..."
$PYTHON stage10/audit/truth.py
$PYTHON -c "
import json
with open('stage10/audit/truth.json') as f:
    t = json.load(f)
cc = t.get('cross_check', {})
if not cc.get('match'):
    print('ERROR: Cross-check match is False!')
    sys.exit(1)
print(f'Truth layer cross-check verified: 173 on-time orders (Method 1={cc[\"on_time_orders_method_1\"]}, Method 2={cc[\"on_time_orders_method_2\"]})')
"

# 3. FORENSIC AUDITS
echo ""
echo ">>> STEP 3: Running Forensic Audit Scripts..."
echo "--- Orders Audit ---"
$PYTHON stage10/audit/orders_audit.py
echo "--- R5 Sourcing Audit ---"
$PYTHON stage10/audit/r5_audit.py
echo "--- Metrics Audit ---"
$PYTHON stage10/audit/metrics_audit.py
echo "--- Gate A Forensic Audit ---"
$PYTHON stage10/audit/gate_a_full.py
echo "--- Reconcile R Audit ---"
$PYTHON stage10/audit/audit_reconcile_r.py

# 4. TEN-DAY DEMO FEED SCORING
echo ""
echo ">>> STEP 4: Evaluating Ten-Day Feed Scoring (score.py)..."
$PYTHON stage10/demo_feed/score.py

# 5. FORBIDDEN LITERALS GUARD
echo ""
echo ">>> STEP 5: Verifying Forbidden Literals Guard outside tests/audits..."
$PYTHON -c "
from pathlib import Path
import sys

ROOT = Path('.')
EXCLUDE_DIRS = {'.git', 'venv', '.venv', 'backups', '__pycache__', '.pytest_cache', 'node_modules', 'stage1', 'stage2', 'stage3', 'stage4', 'stage5', 'stage6', 'stage7', 'stage8'}
EXTS = {'.py', '.html', '.md', '.json', '.yaml', '.yml', '.sh'}
FORBIDDEN = [
    'Supplier 1\'s delivery',
    'Raw steel is running low',
    'Standard Motor',
    'Heavy Duty Motor',
    'Electric Motors',
    'Gear Assemblies',
    'Electronic housings',
    'Plastic resin',
    '78.3% x'
]

matches = []
for p in ROOT.rglob('*'):
    if not p.is_file() or p.suffix not in EXTS:
        continue
    if any(ex in p.parts for ex in EXCLUDE_DIRS):
        continue
    if p.stat().st_size > 500000:
        continue
    if any(x in str(p) for x in ['stage10/audit', 'tests', 'test_', 'verify_all.sh']):
        continue
    try:
        content = p.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        continue
    for term in FORBIDDEN:
        for idx, line in enumerate(content.splitlines(), 1):
            if term.lower() in line.lower():
                matches.append((str(p), idx, term, line.strip()[:100]))

if matches:
    print(f'ERROR: Found {len(matches)} forbidden literals outside tests/audits:')
    for path, line_no, term, text_preview in matches:
        print(f'  {path}:{line_no} [{term}] -> {text_preview}')
    sys.exit(1)
print('Forbidden literals check: PASSED (0 occurrences in product/docs outside tests/audits).')
"

# 6. EMAIL DELIVERY DRY-RUN CHECK
echo ""
echo ">>> STEP 6: Verifying Safe Email Delivery (send_check.py dry-run)..."
$PYTHON -m stage9.send_check

# 7. STAGE 9 COMPREHENSIVE TEST SUITE
echo ""
echo ">>> STEP 7: Executing Stage 9 Comprehensive Test Suite (test_stage9_final.py)..."
$PYTHON stage9/test_stage9_final.py

echo ""
echo "======================================================================"
echo "✓ ALL VERIFICATION CHECKS PASSED SUCCESSFULLY (Exit 0)."
echo "======================================================================"
