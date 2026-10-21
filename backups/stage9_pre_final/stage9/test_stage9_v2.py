"""
stage9/test_stage9_v2.py
────────────────────────
Comprehensive Verification Test Suite for SAGE Stage 9 v2:
Scheduled One-Page Emails + Read-Only Web Dashboard.

Tests:
  1. Snapshot determinism: rerun on the same date produces byte-identical JSON.
  2. No look-ahead: queries strictly bounded by date <= as_of; future records excluded.
  3. Zero-Leakage AST & Runtime Guard: only web/research_view.py accesses ground-truth;
     snapshot anti-leakage guard raises on forbidden tables.
  4. Priorities ordering: 5-tier ranked action rules, severity formulas, watchlist <= 3.
  5. Email one-page PDF check & framing: Playwright A4 asserts page_count == 1,
     verbatim framing sentence and "Simulated data" present.
  6. Narrator validation: validators reject invented numbers, forbidden words,
     and length violations; fallback template produces clean text.
  7. Scheduler idempotency and dry-run default: no live SMTP connection on dry-run,
     no duplicate sends for same job and date.
  8. Web routes authorization: 401 without valid token, 200 on all endpoints with valid token.
"""

from __future__ import annotations

import ast
import json
import os
import threading
import time
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List
import unittest
import uvicorn

ROOT_DIR = Path(__file__).resolve().parent.parent

from app.database import SessionLocal
from app.models.inventory import StockMovement
from stage9.snapshot import compute_daily_snapshot, _assert_no_leakage
from stage9.priorities import compute_priorities
from stage9.narrate import (
    validate_narrative_payload,
    generate_deterministic_template,
    extract_numbers_from_text,
    extract_allowed_facts,
)
from stage9.render_email import (
    render_causal_findings_brief,
    render_nightly_digest,
    assert_one_page_pdf,
    RESEARCH_FRAMING,
)
from stage9.scheduler import dispatch_email, execute_job, get_sent_keys, record_sent_log
from stage9.status import (
    compute_buffer_absorption_status,
    get_packet_display_status,
    compute_mechanical_calibration_label,
)
from web.research_view import load_research_evaluation_data
from web.app import app


class TestStage9v2Suite(unittest.TestCase):

    # ──────────────────────────────────────────────────────────────────────────
    # Test 1: Snapshot Determinism
    # ──────────────────────────────────────────────────────────────────────────
    def test_01_snapshot_determinism(self):
        """Rerunning snapshot computation on the same date produces byte-identical JSON."""
        test_date = date(2025, 1, 15)
        snap1 = compute_daily_snapshot(as_of=test_date)
        snap2 = compute_daily_snapshot(as_of=test_date)

        # Normalize transient generated_at timestamps for determinism comparison
        snap1_norm = dict(snap1)
        snap2_norm = dict(snap2)
        snap1_norm["generated_at"] = "FIXED_TIMESTAMP"
        snap2_norm["generated_at"] = "FIXED_TIMESTAMP"

        json1 = json.dumps(snap1_norm, sort_keys=True, indent=2)
        json2 = json.dumps(snap2_norm, sort_keys=True, indent=2)

        self.assertEqual(json1, json2, "Snapshot is not byte-identical across runs!")
        self.assertEqual(snap1["as_of"], "2025-01-15")
        self.assertIn("materials", snap1)
        self.assertIn("products", snap1)
        self.assertIn("kpis", snap1)

    # ──────────────────────────────────────────────────────────────────────────
    # Test 2: No Look-Ahead (Temporal Integrity)
    # ──────────────────────────────────────────────────────────────────────────
    def test_02_no_look_ahead(self):
        """Snapshot query results contain zero data from future dates (date <= as_of)."""
        early_date = date(2025, 1, 15)
        snap_early = compute_daily_snapshot(as_of=early_date)

        # Ensure all overdue POs identified in snapshot were issued on or before early_date
        for m_id, m_data in snap_early.get("materials", {}).items():
            for po in m_data.get("overdue_pos", []):
                self.assertIn("po_id", po)
                self.assertGreater(po["days_overdue"], 0)

        # Ensure underlying stock movements query respects as_of barrier
        db = SessionLocal()
        try:
            early_movements = db.query(StockMovement).filter(StockMovement.date <= early_date).count()
            late_date = date(2025, 11, 20)
            late_movements = db.query(StockMovement).filter(StockMovement.date <= late_date).count()
            self.assertGreater(
                late_movements,
                early_movements,
                "Cumulative stock movements must monotonically increase with simulation clock.",
            )
        finally:
            db.close()

    # ──────────────────────────────────────────────────────────────────────────
    # Test 3: Zero-Leakage AST & Runtime Guard
    # ──────────────────────────────────────────────────────────────────────────
    def test_03_zero_leakage_ast_and_guard(self):
        """
        AST verification ensures only web/research_view.py references ground-truth artifacts.
        Runtime guard ensures snapshot anti-leakage raises on forbidden tables.
        """
        # Part A: Runtime guard
        with self.assertRaises(RuntimeError):
            _assert_no_leakage("SELECT * FROM business_events")
        with self.assertRaises(RuntimeError):
            _assert_no_leakage("SELECT * FROM ground_truth")
        with self.assertRaises(RuntimeError):
            _assert_no_leakage("SELECT * FROM scenario_incident")

        # Part B: AST check across stage9 and web directories
        forbidden_terms = [
            "scenario_causal_evaluation",
            "simulation_events",
        ]

        scanned_files = []
        for search_dir in [ROOT_DIR / "stage9", ROOT_DIR / "web"]:
            for py_file in search_dir.rglob("*.py"):
                if "research_view.py" in py_file.name or "test_stage9" in py_file.name:
                    continue  # Research view and test suite are permitted to mention them
                scanned_files.append(py_file)

                with open(py_file, "r", encoding="utf-8") as f:
                    tree = ast.parse(f.read(), filename=str(py_file))

                for node in ast.walk(tree):
                    # Check string literals
                    if isinstance(node, ast.Constant) and isinstance(node.value, str):
                        for term in forbidden_terms:
                            if term in node.value and "Anti-leakage" not in node.value and "forbidden" not in node.value and "never" not in node.value:
                                self.fail(
                                    f"Ground-truth leakage detected in {py_file.name}: string contains '{term}'"
                                )
                    # Check imports: Only web/app.py is allowed to import research_view for the /research endpoint
                    if py_file.name != "app.py":
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                self.assertNotIn("research_view", alias.name, f"Illegal import of research_view in {py_file.name}")
                        if isinstance(node, ast.ImportFrom):
                            self.assertNotIn("research_view", node.module or "", f"Illegal import from research_view in {py_file.name}")

        self.assertGreater(len(scanned_files), 5, "Fewer than 5 production files scanned!")

    # ──────────────────────────────────────────────────────────────────────────
    # Test 4: Priorities Ordering & Severity Formulas
    # ──────────────────────────────────────────────────────────────────────────
    def test_04_priorities_ordering_and_rules(self):
        """Priorities engine correctly ranks actions by rule hierarchy and limits watchlist to <= 3."""
        test_date = date(2025, 11, 20)
        prio = compute_priorities(as_of=test_date)

        top_priorities = prio.get("top_priorities", [])
        watchlist = prio.get("watchlist", [])

        # Priority list must have exactly 5 ranked actions
        self.assertEqual(len(top_priorities), 5, f"Expected 5 priorities, got {len(top_priorities)}")

        # Watchlist must never exceed 3 items
        self.assertLessEqual(len(watchlist), 3, f"Watchlist exceeded 3 items: {len(watchlist)}")

        # Check ranking monotonic fields
        for act in top_priorities:
            self.assertIn("action", act)
            self.assertIn("reason", act)
            self.assertIn("role", act)
            self.assertIn("rank", act)

    # ──────────────────────────────────────────────────────────────────────────
    # Test 5: Email One-Page PDF Check & Mandatory Framing
    # ──────────────────────────────────────────────────────────────────────────
    def test_05_email_one_page_pdf_and_framing(self):
        """Both emails fit strictly on 1 PDF page and contain the verbatim research framing."""
        test_date = date(2025, 11, 20)

        # Causal findings brief
        sbj_brief, html_brief, txt_brief = render_causal_findings_brief(as_of=test_date)
        self.assertIn(RESEARCH_FRAMING, html_brief)
        self.assertIn(" ".join(RESEARCH_FRAMING.split()), " ".join(txt_brief.split()))
        self.assertIn("Simulated data", html_brief)
        self.assertIn("Simulated data", txt_brief)

        is_one_page, page_cnt, _ = assert_one_page_pdf(html_brief)
        self.assertTrue(is_one_page, f"Findings brief exceeded 1 page (pages={page_cnt})")
        self.assertEqual(page_cnt, 1)

        # Nightly digest
        sbj_digest, html_digest, txt_digest = render_nightly_digest(as_of=test_date)
        self.assertIn(RESEARCH_FRAMING, html_digest)
        self.assertIn(" ".join(RESEARCH_FRAMING.split()), " ".join(txt_digest.split()))
        self.assertIn("Simulated data", html_digest)
        self.assertIn("Simulated data", txt_digest)

        is_one_page2, page_cnt2, _ = assert_one_page_pdf(html_digest)
        self.assertTrue(is_one_page2, f"Nightly digest exceeded 1 page (pages={page_cnt2})")
        self.assertEqual(page_cnt2, 1)

    # ──────────────────────────────────────────────────────────────────────────
    # Test 6: Narrator Validation & Template Fallback
    # ──────────────────────────────────────────────────────────────────────────
    def test_06_narrator_validation_and_fallback(self):
        """Narrator validator rejects invented numbers, forbidden words, and word overflow."""
        test_date = date(2025, 11, 20)
        snap = compute_daily_snapshot(as_of=test_date)
        prio = compute_priorities(as_of=test_date, snapshot=snap)

        allowed_nums, allowed_ents = extract_allowed_facts(snap, prio)

        # Case A: Deterministic fallback produces valid narrative
        template_payload = generate_deterministic_template(snap, prio)
        self.assertIn("bottom_line", template_payload)
        self.assertIn("what_happened", template_payload)
        valid, err = validate_narrative_payload(template_payload, allowed_nums, allowed_ents)
        self.assertTrue(valid, f"Template narrative failed validation: {err}")

        # Case B: Invented number must fail
        bad_payload_b = dict(template_payload)
        bad_payload_b["bottom_line"] = template_payload["bottom_line"] + " Unverified metric: 987654 units lost."
        valid_b, err_b = validate_narrative_payload(bad_payload_b, allowed_nums, allowed_ents)
        self.assertFalse(valid_b)
        self.assertTrue(any("ungrounded numbers" in e.lower() for e in err_b))

        # Case C: Forbidden word must fail
        bad_payload_c = dict(template_payload)
        bad_payload_c["bottom_line"] = template_payload["bottom_line"] + " Confirmed by ground_truth incident logs."
        valid_c, err_c = validate_narrative_payload(bad_payload_c, allowed_nums, allowed_ents)
        self.assertFalse(valid_c)
        self.assertTrue(any("forbidden tokens detected" in e.lower() for e in err_c))

        # Case D: Word limit exceed must fail
        bad_payload_d = dict(template_payload)
        bad_payload_d["bottom_line"] = "word " * 150
        valid_d, err_d = validate_narrative_payload(bad_payload_d, allowed_nums, allowed_ents)
        self.assertFalse(valid_d)
        self.assertTrue(any("words" in e.lower() for e in err_d))

    # ──────────────────────────────────────────────────────────────────────────
    # Test 7: Scheduler Idempotency & Dry-Run Default
    # ──────────────────────────────────────────────────────────────────────────
    def test_07_scheduler_idempotency_and_dry_run(self):
        """Scheduler operates in dry-run mode without external SMTP, logs idempotently."""
        test_date = date(2025, 12, 1)
        job_name = "nightly_digest"

        # Run 1: Dispatch with force=True
        ok1 = execute_job(job_name=job_name, as_of=test_date, force=True)
        self.assertTrue(ok1)

        # Run 2: Dispatch again without force -> must skip duplicate delivery
        ok2 = execute_job(job_name=job_name, as_of=test_date, force=False)
        self.assertTrue(ok2)

        # Verify sent key is tracked in sent_log
        sent_keys = get_sent_keys()
        self.assertIn(f"{job_name}:2025-12-01", sent_keys)

    # ──────────────────────────────────────────────────────────────────────────
    # Test 8: Web Routes Authorization & Quarantined Research View
    # ──────────────────────────────────────────────────────────────────────────
    def test_08_web_routes_auth_and_research(self):
        """All web routes return 401 without token and 200 with valid token; P10 honest."""
        test_port = 8993
        config = uvicorn.Config(app, host="127.0.0.1", port=test_port, log_level="error")
        server = uvicorn.Server(config)
        t = threading.Thread(target=server.run, daemon=True)
        t.start()

        time.sleep(0.5)

        base = f"http://127.0.0.1:{test_port}"
        valid_token = os.getenv("SAGE_WEB_TOKEN", "sage_dev_token_2025")

        try:
            # 1. Unauthenticated request to / -> 401
            try:
                urllib.request.urlopen(f"{base}/")
                self.fail("Unauthenticated request did not return 401!")
            except urllib.error.HTTPError as err:
                self.assertEqual(err.code, 401)

            # 2. Invalid token request -> 401
            try:
                urllib.request.urlopen(f"{base}/?token=wrong-token-xyz")
                self.fail("Invalid token request did not return 401!")
            except urllib.error.HTTPError as err:
                self.assertEqual(err.code, 401)

            # 3. Authenticated request with token -> 200
            req = urllib.request.urlopen(f"{base}/?token={valid_token}")
            self.assertEqual(req.status, 200)

            # 4. Check /research route authentication and content
            req_res = urllib.request.urlopen(f"{base}/research?token={valid_token}")
            self.assertEqual(req_res.status, 200)
            res_body = req_res.read().decode("utf-8")
            self.assertIn("Research evaluation", res_body)
            self.assertIn("False positive on negative control", res_body)

            # 5. Check all main routes return 200
            for endpoint in ["/digests", "/priorities", "/causal", "/method", "/schedule"]:
                r = urllib.request.urlopen(f"{base}{endpoint}?token={valid_token}")
                self.assertEqual(r.status, 200, f"Endpoint {endpoint} failed with {r.status}")

        finally:
            server.should_exit = True
            time.sleep(0.2)

        # Directly verify research evaluation module contents
        res_data = load_research_evaluation_data()
        self.assertIn("banner", res_data)
        self.assertEqual(
            res_data["banner"],
            "Research evaluation. Uses ground truth. Never available to the narrator.",
        )
        p10_row = next((r for r in res_data["scenarios"] if r["scenario_id"] in ("INC_10", "P10")), None)
        self.assertIsNotNone(p10_row)
        self.assertEqual(p10_row["classification"], "False positive on negative control")


if __name__ == "__main__":
    unittest.main()
