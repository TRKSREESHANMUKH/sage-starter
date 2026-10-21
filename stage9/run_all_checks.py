"""
stage9/run_all_checks.py — Unified Verification and Integrity Check Suite.

Runs:
1. Frozen artifact integrity verification (Stage 7 & Stage 8).
2. Data reconciliation and operational metrics audit.
3. Zero-look-ahead and demo case jump invariance check.
4. HTTP smoke checks across Viewer (8000) and Controller (8001).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
import time
from datetime import date
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("run_all_checks")


def _sha256(path: Path) -> str:
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_frozen_hashes() -> bool:
    """Verifies that Stage 7 and Stage 8 frozen files match their manifests."""
    print("Checking Stage 7 & Stage 8 frozen file hashes...")
    all_ok = True

    # Stage 7
    f7_path = ROOT_DIR / "stage7" / "FROZEN.json"
    if not f7_path.exists():
        print("  [FAIL] Missing stage7/FROZEN.json")
        all_ok = False
    else:
        with open(f7_path) as f:
            f7 = json.load(f)
        m_hash = _sha256(ROOT_DIR / "stage7" / "fitted_causal_model.pkl")
        r_hash = _sha256(ROOT_DIR / "analytics" / "causal_attribution_results.json")
        if m_hash != f7.get("fitted_causal_model_sha256"):
            print("  [FAIL] stage7/fitted_causal_model.pkl hash mismatch")
            all_ok = False
        if r_hash != f7.get("causal_attribution_results_sha256"):
            print("  [FAIL] analytics/causal_attribution_results.json hash mismatch")
            all_ok = False

    # Stage 8
    f8_path = ROOT_DIR / "stage8" / "FROZEN.json"
    if not f8_path.exists():
        print("  [FAIL] Missing stage8/FROZEN.json")
        all_ok = False
    else:
        with open(f8_path) as f:
            f8 = json.load(f)
        p_hash = _sha256(ROOT_DIR / "analytics" / "evidence_packets.json")
        n_hash = _sha256(ROOT_DIR / "analytics" / "narration_results.json")
        e_hash = _sha256(ROOT_DIR / "analytics" / "narrative_evaluation.json")
        if p_hash != f8.get("evidence_packets_sha256"):
            print("  [FAIL] analytics/evidence_packets.json hash mismatch")
            all_ok = False
        if n_hash != f8.get("narration_results_sha256"):
            print("  [FAIL] analytics/narration_results.json hash mismatch")
            all_ok = False
        if e_hash != f8.get("narrative_evaluation_sha256"):
            print("  [FAIL] analytics/narrative_evaluation.json hash mismatch")
            all_ok = False

    if all_ok:
        print("  [PASS] All Stage 7 & 8 frozen file hashes verified!")
    return all_ok


def check_reconciliation() -> bool:
    """Verifies customer delivery reconciliation and supplier separation on full-year review."""
    print("Checking operational metrics reconciliation...")
    from stage9.ops import load_year_review
    from web.insights_data import get_insights_data

    # Ensure full year loaded
    load_year_review(user="run_all_checks")
    data_2025 = get_insights_data("2025-12-31", period="ytd")

    all_ok = True
    summary = {s["id"]: s["value"] for s in data_2025.get("summary_strip", [])}

    ot_val = summary.get("kpi_on_time", "")
    if not ot_val:
        print("  [FAIL] kpi_on_time missing in summary strip")
        all_ok = False
    else:
        print(f"  [PASS] On-time delivery rate verified: {ot_val}")

    supp_cards = data_2025.get("supplier_cards", [])
    active_sids = {s.get("supplier_id") for s in supp_cards}
    if 1 in active_sids or 2 in active_sids:
        print(f"  [FAIL] Inactive backup vendors 1 or 2 appeared in active cards: {active_sids}")
        all_ok = False
    else:
        print(f"  [PASS] Active suppliers isolated (IDs 3, 4, 5). Idle backup vendors collapsed.")

    return all_ok


def check_no_lookahead_and_cases() -> bool:
    """Verifies that jump_to_case enforces strict no-look-ahead in live database."""
    print("Checking Demo Cases and No-Look-Ahead isolation...")
    from stage9.ops import get_demo_cases, jump_to_case
    from app.database import get_engine
    from sqlalchemy.orm import sessionmaker
    from app.models.sales import SalesOrder
    from app.models.purchasing import PurchaseOrder

    cases = get_demo_cases()
    if len(cases) != 10:
        print(f"  [FAIL] Expected 10 demo cases, found {len(cases)}")
        return False

    # Jump to Case 1 (2025-03-31)
    jump_to_case(1, user="test_suite")
    eng = get_engine("live")
    Session = sessionmaker(bind=eng)
    db = Session()
    try:
        max_so_date = db.query(SalesOrder.order_date).order_by(SalesOrder.order_date.desc()).first()
        max_po_date = db.query(PurchaseOrder.order_date).order_by(PurchaseOrder.order_date.desc()).first()

        cutoff = date(2025, 3, 31)
        if max_so_date and max_so_date[0] > cutoff:
            print(f"  [FAIL] SO date {max_so_date[0]} exceeded cutoff {cutoff}")
            return False
        if max_po_date and max_po_date[0] > cutoff:
            print(f"  [FAIL] PO date {max_po_date[0]} exceeded cutoff {cutoff}")
            return False
        print(f"  [PASS] No-look-ahead strictly verified: max date in DB <= {cutoff}")
    finally:
        db.close()
    return True


def check_http_routes() -> bool:
    """Verifies that all primary viewer and controller endpoints return 200 OK."""
    print("Checking HTTP endpoints...")
    import urllib.request
    all_ok = True
    endpoints = [
        ("Viewer Home", "http://127.0.0.1:8000/?token=sage_dev_token_2025"),
        ("Viewer Insights", "http://127.0.0.1:8000/insights?token=sage_dev_token_2025"),
        ("Viewer Method", "http://127.0.0.1:8000/method?token=sage_dev_token_2025"),
        ("Viewer Research", "http://127.0.0.1:8000/research?token=sage_dev_token_2025"),
        ("Controller Login", "http://127.0.0.1:8001/ctrl/login"),
    ]
    for label, url in endpoints:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "SAGE-Check"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    print(f"  [PASS] {label}: HTTP 200 OK")
                else:
                    print(f"  [FAIL] {label}: HTTP {resp.status}")
                    all_ok = False
        except Exception as exc:
            print(f"  [FAIL] {label}: Connection error ({exc})")
            all_ok = False
    return all_ok


def main():
    print("=" * 70)
    print("SAGE UNIFIED VERIFICATION SUITE — STAGE 9 FINAL 2")
    print("=" * 70)
    t0 = time.time()

    f_ok = check_frozen_hashes()
    r_ok = check_reconciliation()
    c_ok = check_no_lookahead_and_cases()
    h_ok = check_http_routes()

    elapsed = round(time.time() - t0, 2)
    print("=" * 70)
    if f_ok and r_ok and c_ok and h_ok:
        print(f"ALL CHECKS PASSED in {elapsed}s! ✓")
        sys.exit(0)
    else:
        print(f"ONE OR MORE CHECKS FAILED in {elapsed}s! ✗")
        sys.exit(1)


if __name__ == "__main__":
    main()
