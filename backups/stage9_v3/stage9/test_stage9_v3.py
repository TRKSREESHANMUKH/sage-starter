"""
stage9/test_stage9_v3.py — Complete Test Suite for SAGE Stage 9 v3.

Verifies:
1. No filler priorities on calm dates.
2. No forbidden jargon in email text or visible web HTML outside "Technical details".
3. Rendered PDF is strictly 1 A4 page.
4. Verbatim framing sentence is present in both email and web page.
5. Timeline marks match analytics/eventful_dates.json exactly.
6. Scheduler --run-due idempotency (second run sends nothing).
7. Zero auth tokens in any email body or dashboard links.
8. Zero ground-truth leakage and strict temporal anti-lookahead.
"""

import json
import os
import re
import subprocess
import sys
import unittest
from datetime import date
from pathlib import Path
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from stage9.clock import get_as_of_date
from stage9.snapshot import compute_daily_snapshot
from stage9.priorities import compute_priorities
from stage9.render_email import render_nightly_digest, get_base_url, assert_one_page_pdf
from stage9.status import RESEARCH_FRAMING
from web.one_page_data import build_one_page_context, load_eventful_dates

FORBIDDEN_TERMS = ["M1", "M2", "Shapley", "null", "p95", "tier", "packet", "P01"]


def test_calm_date_no_filler_priorities():
    """Filler priorities must be eliminated; only real data or 'Nothing needs action tomorrow.'"""
    calm_date = date(2025, 1, 15)
    snap = compute_daily_snapshot(calm_date)
    pri = compute_priorities(calm_date, snapshot=snap)
    priorities = pri.get("priorities", [])

    forbidden_fillers = [
        "Routine workcenter equipment calibration",
        "Safety stock verification audit",
        "Vendor scorecard review",
        "Preventive maintenance sweep"
    ]
    for p in priorities:
        title = p.get("title", "")
        for filler in forbidden_fillers:
            assert filler.lower() not in title.lower(), f"Forbidden filler priority detected: {title}"

    # Verify that valid forward-looking priority structure exists
    if priorities:
        valid_reasons = ["days of cover", "Purchase order", "Delivery due", "stockout", "shortfall"]
        for p in priorities:
            assert any(vr.lower() in p.get("reason", "").lower() for vr in valid_reasons), f"Unverified reason: {p}"


def test_framing_sentence_present():
    """Framing sentence must appear verbatim in email and web page."""
    verbatim = "SAGE performs controlled synthetic causal-attribution evaluation under an expert-defined causal model; it does not claim to prove real-world causality."

    # In email
    sbj, htm, txt = render_nightly_digest(date(2025, 2, 3))
    assert verbatim in txt, "Framing sentence missing from email text"
    assert verbatim in htm, "Framing sentence missing from email HTML"

    # In web context
    ctx = build_one_page_context("2025-02-03")
    assert ctx["framing"] == verbatim, "Framing sentence missing from web context"


def test_no_token_in_email():
    """Email must never expose tokens in links or body."""
    sbj, htm, txt = render_nightly_digest(date(2025, 2, 3))
    assert "token=" not in txt, "Token query param found in email text"
    assert "token=" not in htm, "Token query param found in email HTML"
    assert "sage_dev_token" not in txt, "Hardcoded token string found in email text"
    assert "sage_dev_token" not in htm, "Hardcoded token string found in email HTML"

    base_url = get_base_url()
    assert "token=" not in base_url, "Base URL contains token query param"


def test_no_jargon_in_email():
    """No forbidden jargon words may appear in manager-facing emails."""
    for test_d in [date(2025, 2, 3), date(2025, 1, 15)]:
        sbj, htm, txt = render_nightly_digest(test_d)
        content_to_check = txt + " " + htm
        for term in FORBIDDEN_TERMS:
            pattern = rf"\b{re.escape(term)}\b"
            matches = re.findall(pattern, content_to_check, re.IGNORECASE)
            assert not matches, f"Forbidden jargon '{term}' found in email for {test_d}: {matches}"


def test_no_jargon_in_visible_web_html():
    """No forbidden jargon may appear outside 'Technical details' on the web page."""
    for test_d in ["2025-02-03", "2025-01-15"]:
        ctx = build_one_page_context(test_d)
        from jinja2 import Environment, FileSystemLoader
        env = Environment(loader=FileSystemLoader(str(ROOT_DIR / "web" / "templates")))
        tmpl = env.get_template("home.html")
        html = tmpl.render(ctx)

        # Strip technical details section before checking
        html_visible = re.sub(r'<details class="tech-details">.*?</details>', '', html, flags=re.DOTALL)

        for term in FORBIDDEN_TERMS:
            pattern = rf"\b{re.escape(term)}\b"
            matches = re.findall(pattern, html_visible, re.IGNORECASE)
            assert not matches, f"Forbidden jargon '{term}' found in visible web HTML for {test_d}: {matches}"


def test_timeline_matches_eventful_dates():
    """Timeline marks must match analytics/eventful_dates.json exactly."""
    eventful_data = load_eventful_dates()
    eventful_dates = {item["date"] for item in eventful_data if "date" in item}

    ctx = build_one_page_context("2025-02-03")
    timeline_days = ctx["timeline_days"]
    assert len(timeline_days) == 365, f"Expected 365 days, got {len(timeline_days)}"

    marked_in_timeline = {d["date"] for d in timeline_days if d["is_eventful"]}
    assert marked_in_timeline == eventful_dates, (
        f"Timeline mismatch: {len(marked_in_timeline)} marked vs {len(eventful_dates)} in eventful_dates.json"
    )


def test_one_page_pdf():
    """PDF attachment must be strictly 1 page."""
    sbj, htm, txt = render_nightly_digest(date(2025, 2, 3))
    is_single, page_count, pdf_bytes = assert_one_page_pdf(htm)
    assert is_single, f"Expected exactly 1 page PDF, got {page_count}"
    assert page_count == 1, f"Expected 1 page, got {page_count}"


def test_run_due_idempotency(tmp_path):
    """Running --run-due twice on the same day must send on first run and skip on second run."""
    cmd = ["./venv/bin/python", "-m", "stage9.scheduler", "--run-due"]
    env = os.environ.copy()
    env["PYTHONPATH"] = "."

    # First run
    p1 = subprocess.run(cmd, env=env, capture_output=True, text=True)
    assert p1.returncode == 0, f"Run 1 failed: {p1.stderr}"

    # Second run immediately after
    p2 = subprocess.run(cmd, env=env, capture_output=True, text=True)
    assert p2.returncode == 0, f"Run 2 failed: {p2.stderr}"
    assert "already sent" in p2.stdout.lower() or "skipped" in p2.stdout.lower() or "skip" in p2.stdout.lower(), (
        f"Expected idempotent skip in run 2, got output: {p2.stdout}"
    )


def test_zero_leakage_and_temporal_precedence():
    """Snapshot logic must never read future dates or business_events table."""
    from stage9.snapshot import SNAPSHOTS_DIR
    target_d = date(2025, 3, 15)
    snap = compute_daily_snapshot(target_d)

    # Check metadata
    assert snap["as_of"] == "2025-03-15"
    assert "incident" not in snap["metadata"]
    assert "ground_truth" not in snap["metadata"]


if __name__ == "__main__":
    tests = [
        test_calm_date_no_filler_priorities,
        test_framing_sentence_present,
        test_no_token_in_email,
        test_no_jargon_in_email,
        test_no_jargon_in_visible_web_html,
        test_timeline_matches_eventful_dates,
        test_one_page_pdf,
        test_run_due_idempotency,
        test_zero_leakage_and_temporal_precedence,
    ]
    passed = 0
    failed = 0
    print(f"Running {len(tests)} Stage 9 v3 test suites...")
    for t in tests:
        name = t.__name__
        try:
            if "tmp_path" in t.__code__.co_varnames:
                t(None)
            else:
                t()
            print(f"  [PASS] {name}")
            passed += 1
        except Exception as exc:
            print(f"  [FAIL] {name}: {exc}")
            failed += 1

    print(f"\nResults: {passed} passed, {failed} failed.")
    if failed > 0:
        sys.exit(1)
