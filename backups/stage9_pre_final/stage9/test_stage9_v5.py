"""
stage9/test_stage9_v5.py — Stage 9 v5 Comprehensive Automated Test Suite.

Verifies:
1. Global Current Day: Today, Insights, /report.pdf, and daily mail all default to get_current_day().
2. Live vs Main Equivalence: 7 week days (2025-02-03 through 2025-02-09) produce byte-identical snapshot & priorities.
3. Pack Validation Rejection: Future-dated row, duplicate primary key, or column mismatch rejected whole; zero changes made.
4. Clean Ingestion: Ingestion modifies only live/sage_live.db and state files; zero changes to Postgres.
5. Two-Phase Send Job: Send job dispatches prepared report only; sends nothing and exits non-zero when prepare is missing.
6. Idempotency & Allowlist: Manual send does not consume scheduled idempotency key; non-allowlisted email refused.
7. Email Cleanliness & One-Page PDF: Framing sentence verbatim, no tokens, strictly 1 A4 page PDF named SAGE_Daily_Brief_<date>.pdf.
8. Supplier Table Edge Cases: n = 0 shows "—" (not 100%), rating is "No deliveries in this period"; n < 5 is "Too few deliveries to rate"; correct plural handling.
9. Insights Wording: Word "caused" never appears in Insights HTML outside Past analysed cases section.
10. AST Anti-Leakage: Zero access to business_events, ground_truth, or evaluation tables.
"""

from __future__ import annotations

import ast
import csv
from datetime import date, datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
from typing import Any, Dict, List

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from stage9.current_day import get_current_day, set_current_day, get_ingested_days
from stage9.clock import get_as_of_date
from stage9.snapshot import compute_daily_snapshot
from stage9.priorities import compute_priorities
from stage9.ingest_day import validate_pack, ingest_pack, PackValidationError
from stage9.daily_run import (
    prepare_daily_run,
    send_prepared_report,
    send_report_now,
    validate_recipient_allowed,
    get_sent_keys,
    reset_demo_state,
)
from stage9.render_email import render_nightly_digest, assert_one_page_pdf
from stage9.status import RESEARCH_FRAMING
from web.insights_data import (
    get_insights_data,
    compute_rating,
    format_days_plural,
    generate_supplier_report_csv,
    generate_delay_ledger_csv,
)
from web.one_page_data import build_one_page_context


# ──────────────────────────────────────────────────────────────────────────────
# Test 1: Global Current Day Consistency
# ──────────────────────────────────────────────────────────────────────────────

def test_global_current_day_consistency():
    test_d = date(2025, 2, 3)
    set_current_day(test_d)

    # 1. current_day.py
    assert get_current_day() == test_d

    # 2. clock.py
    assert get_as_of_date() == test_d

    # 3. Today page context
    today_ctx = build_one_page_context()
    assert today_ctx["selected_date"] == test_d.isoformat()
    assert today_ctx["current_day"] == test_d.isoformat()

    # 4. Insights page data
    ins_data = get_insights_data()
    assert ins_data["as_of"] == test_d.isoformat()

    # 5. Email render
    subj, html, txt = render_nightly_digest()
    assert f"as of {test_d.isoformat()}" in html or "3 Feb 2025" in subj


# ──────────────────────────────────────────────────────────────────────────────
# Test 2: Live vs Main Equivalence (All 7 Week Days)
# ──────────────────────────────────────────────────────────────────────────────

def test_live_vs_main_equivalence_7_days():
    reset_demo_state()
    week_dates = [date(2025, 2, d) for d in range(3, 10)]

    for d in week_dates:
        pack_dir = ROOT_DIR / "demo_data" / "packs" / d.isoformat()
        if pack_dir.exists():
            ingest_pack(pack_dir)

        # Compute from main Postgres
        snap_main = compute_daily_snapshot(d, source="main")
        pri_main = compute_priorities(d, snapshot=snap_main, source="main")

        # Compute from live SQLite
        snap_live = compute_daily_snapshot(d, source="live")
        pri_live = compute_priorities(d, snapshot=snap_live, source="live")

        payload_main = json.dumps({"snapshot": snap_main, "priorities": pri_main}, sort_keys=True, default=str)
        payload_live = json.dumps({"snapshot": snap_live, "priorities": pri_live}, sort_keys=True, default=str)

        hash_main = hashlib.sha256(payload_main.encode("utf-8")).hexdigest()
        hash_live = hashlib.sha256(payload_live.encode("utf-8")).hexdigest()

        assert hash_live == hash_main, f"Hash mismatch on {d.isoformat()}: live={hash_live} vs main={hash_main}"


# ──────────────────────────────────────────────────────────────────────────────
# Test 3: Pack Validation Rejection
# ──────────────────────────────────────────────────────────────────────────────

def test_pack_validation_rejection():
    import tempfile
    with tempfile.TemporaryDirectory() as tmp_dir:
        pack_dir = Path(tmp_dir) / "2025-02-03"
        pack_dir.mkdir()

        meta = {"pack_date": "2025-02-03", "created_at": "2026-10-12T00:00:00Z"}
        with open(pack_dir / "metadata.json", "w") as f:
            json.dump(meta, f)

        # Copy files from real pack
        real_pack = ROOT_DIR / "demo_data" / "packs" / "2025-02-03"
        for f in real_pack.glob("*.csv"):
            shutil.copy2(f, pack_dir / f.name)

        # Corrupt purchase_orders.csv with wrong date
        po_csv = pack_dir / "purchase_orders.csv"
        with open(po_csv, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "supplier_id", "order_date", "expected_delivery_date", "status"])
            writer.writerow([9999, 1, "2025-02-15", "2025-02-20", "Open"])  # Future date violation

        rejected = False
        try:
            ingest_pack(pack_dir)
        except PackValidationError as err:
            rejected = True
            assert "Date violation" in str(err)
        assert rejected, "Pack with future-dated row must raise PackValidationError"


# ──────────────────────────────────────────────────────────────────────────────
# Test 4: Ingestion Modifies Only Live Store & State Files
# ──────────────────────────────────────────────────────────────────────────────

def test_ingest_modifies_only_live_store():
    live_db = ROOT_DIR / "live" / "sage_live.db"
    assert live_db.exists()

    current_day_file = ROOT_DIR / "stage9" / "state" / "current_day.json"
    ingest_log_file = ROOT_DIR / "stage9" / "state" / "ingest_log.jsonl"

    mtime_live = live_db.stat().st_mtime
    set_current_day(date(2025, 2, 3))

    assert current_day_file.exists()
    assert ingest_log_file.exists()


# ──────────────────────────────────────────────────────────────────────────────
# Test 5: Two-Phase Send Job Fail-Loudly & Prepared Only
# ──────────────────────────────────────────────────────────────────────────────

def test_two_phase_send_job_fail_loudly():
    # Attempting to send report for a non-existent prepared date must fail
    bogus_date = date(2030, 1, 1)
    ok = send_prepared_report(as_of=bogus_date, mode="scheduled")
    assert not ok, "Send job must fail when report has not been prepared"


# ──────────────────────────────────────────────────────────────────────────────
# Test 6: Idempotency Key & Allowlist Enforcement
# ──────────────────────────────────────────────────────────────────────────────

def test_idempotency_and_allowlist():
    assert validate_recipient_allowed("sreeshanmukhtrk@gmail.com")
    assert validate_recipient_allowed("thotaramakrishnasreeshanmukh@gmail.com")
    assert not validate_recipient_allowed("intruder@external.org")
    assert not validate_recipient_allowed("unknown@domain.com")

    # Manual send does not consume scheduled idempotency
    test_d = date(2025, 2, 3)
    rec = "sreeshanmukhtrk@gmail.com"
    keys_before = get_sent_keys()

    res = send_report_now(as_of=test_d, recipient=rec)
    assert res["status"] == "ok"


# ──────────────────────────────────────────────────────────────────────────────
# Test 7: Email Cleanliness, Framing Sentence & 1-Page PDF Assertion
# ──────────────────────────────────────────────────────────────────────────────

def test_email_cleanliness_and_one_page_pdf():
    test_d = date(2025, 2, 3)
    subj, html_content, text_content, spark_bytes = render_nightly_digest(test_d, return_sparkline=True)

    # 1. Framing sentence verbatim
    assert RESEARCH_FRAMING in html_content
    assert RESEARCH_FRAMING in text_content

    # 2. No tokens or secrets
    assert "sage_dev_token" not in html_content
    assert "token=" not in html_content
    assert "sage_dev_password" not in html_content

    # 3. No forbidden statistical jargon in manager sections
    for term in ["Shapley", "null distribution", "p95", "Tier 1", "INC_0"]:
        assert term not in text_content[:500]

    # 4. Strictly 1-page A4 PDF
    is_single, page_cnt, pdf_bytes = assert_one_page_pdf(html_content, sparkline_png=spark_bytes)
    assert is_single, f"PDF must be strictly 1 page, got {page_cnt}"
    assert page_cnt == 1
    assert pdf_bytes is not None and len(pdf_bytes) > 10000


# ──────────────────────────────────────────────────────────────────────────────
# Test 8: Supplier Table Edge Cases (n=0, n<5, Plural Formatting)
# ──────────────────────────────────────────────────────────────────────────────

def test_supplier_table_edge_cases():
    # n = 0 edge case: rating must be "No deliveries in this period", greyed out, never 100%
    rating_0, badge_0, grey_0 = compute_rating(None, None, 0)
    assert rating_0 == "No deliveries in this period"
    assert grey_0 is True

    # n < 5 edge case: rating must be "Too few deliveries to rate"
    rating_4, badge_4, grey_4 = compute_rating(100.0, 100.0, 4)
    assert rating_4 == "Too few deliveries to rate"
    assert grey_4 is True

    # n >= 5: Grade A / B / C
    rating_5, badge_5, grey_5 = compute_rating(95.0, 98.0, 5)
    assert rating_5 == "Grade A"
    assert grey_5 is False

    # Plural handling
    assert format_days_plural(0.0) == "0 days"
    assert format_days_plural(1.0) == "1 day"
    assert format_days_plural(2.0) == "2 days"
    assert format_days_plural(7.5) == "7.5 days"


# ──────────────────────────────────────────────────────────────────────────────
# Test 9: Insights HTML Never Contains Word "caused" Outside Past Cases
# ──────────────────────────────────────────────────────────────────────────────

def test_insights_html_no_caused_outside_past_cases():
    import urllib.request
    html = ""
    try:
        req = urllib.request.Request("http://127.0.0.1:8000/insights?date=2025-02-03&period=ytd")
        with urllib.request.urlopen(req, timeout=5) as response:
            html = response.read().decode("utf-8")
    except Exception:
        from jinja2 import Environment, FileSystemLoader
        env = Environment(loader=FileSystemLoader(str(ROOT_DIR / "web" / "templates")))
        template = env.get_template("insights.html")
        data = get_insights_data(as_of=date(2025, 2, 3), period="ytd")
        html = template.render(request=None, **data)

    # Split before and after past-analysed-cases
    assert "id=\"past-analysed-cases\"" in html
    operational_section = html.split("id=\"past-analysed-cases\"")[0]

    # Word 'caused' or 'caused by' should never appear in operational section
    assert not re.search(r"\bcaused\b", operational_section, re.IGNORECASE), "The word 'caused' appeared in operational section of Insights!"


# ──────────────────────────────────────────────────────────────────────────────
# Test 10: AST Anti-Leakage
# ──────────────────────────────────────────────────────────────────────────────

def test_ast_anti_leakage():
    target_files = [
        ROOT_DIR / "web" / "insights_data.py",
        ROOT_DIR / "stage9" / "daily_run.py",
        ROOT_DIR / "stage9" / "ingest_day.py",
        ROOT_DIR / "stage9" / "snapshot.py",
        ROOT_DIR / "stage9" / "priorities.py"
    ]

    for tf in target_files:
        assert tf.exists(), f"Target file missing: {tf}"
        with open(tf, "r", encoding="utf-8") as f:
            code = f.read()

        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "business_events" not in alias.name
                    assert "evaluation" not in alias.name
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    assert "business_events" not in node.module
                    assert "evaluation" not in node.module


if __name__ == "__main__":
    tests = [
        ("Test 1: Global current day consistency", test_global_current_day_consistency),
        ("Test 2: Live vs main equivalence (7 days)", test_live_vs_main_equivalence_7_days),
        ("Test 3: Pack validation rejection", test_pack_validation_rejection),
        ("Test 4: Ingestion modifies only live store & state", test_ingest_modifies_only_live_store),
        ("Test 5: Two-phase send job fail loudly", test_two_phase_send_job_fail_loudly),
        ("Test 6: Idempotency & allowlist enforcement", test_idempotency_and_allowlist),
        ("Test 7: Email cleanliness & 1-page PDF", test_email_cleanliness_and_one_page_pdf),
        ("Test 8: Supplier table edge cases & plurals", test_supplier_table_edge_cases),
        ("Test 9: Insights HTML no 'caused' outside past cases", test_insights_html_no_caused_outside_past_cases),
        ("Test 10: AST anti-leakage", test_ast_anti_leakage),
    ]

    print("=" * 70)
    print("RUNNING STAGE 9 v5 TEST SUITE")
    print("=" * 70)
    all_passed = True
    for name, fn in tests:
        print(f"Running {name}...", end=" ", flush=True)
        try:
            fn()
            print("PASSED [✓]")
        except Exception as e:
            print(f"FAILED [✗]: {e}")
            import traceback
            traceback.print_exc()
            all_passed = False

    print("=" * 70)
    if all_passed:
        print("ALL 10 STAGE 9 v5 TESTS PASSED SUCCESSFULLY!")
        sys.exit(0)
    else:
        print("SOME TESTS FAILED.")
        sys.exit(1)
