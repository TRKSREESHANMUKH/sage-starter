"""
stage9/test_stage9.py
──────────────────────
Test suite for SAGE Stage 9 (Reporting, APScheduler, and SMTP).

Verifies:
  1. Report builder produces valid HTML, plain-text, and subject.
  2. Research framing is present verbatim in both HTML and text reports.
  3. MIME multipart/alternative structure is correctly configured.
  4. SMTP dry-run delivers receipts without network dependencies.
  5. APScheduler successfully registers the cron trigger and runs on-demand jobs.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

from stage8.common import ANALYTICS_DIR, EvidencePacket
from stage9.report_builder import build_html_report, build_subject, build_text_report
from stage9.scheduler import generate_and_dispatch_report, setup_scheduler
from stage9.smtp_sender import create_mime_message, send_report

NARRATION_PATH = ANALYTICS_DIR / "narration_results.json"


class TestStage9Reporting(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not NARRATION_PATH.exists():
            raise unittest.SkipTest("analytics/narration_results.json missing; run Stage 8 first.")
        with NARRATION_PATH.open() as fh:
            cls.narration_data = json.load(fh)

    def test_01_report_builder_text(self):
        text = build_text_report(self.narration_data)
        self.assertIn("SAGE Causal Attribution Report", text)
        self.assertIn(EvidencePacket.RESEARCH_FRAMING, text)
        self.assertIn("Packet   : P01", text)
        self.assertIn("Manager Narrative:", text)

    def test_02_report_builder_html(self):
        html_out = build_html_report(self.narration_data)
        self.assertIn("<!DOCTYPE html>", html_out)
        self.assertIn("SAGE Causal Attribution Report", html_out)
        self.assertIn(EvidencePacket.RESEARCH_FRAMING, html_out)
        self.assertIn("Evidence Drivers", html_out)
        self.assertIn("P01", html_out)

    def test_03_report_builder_subject(self):
        subject = build_subject(self.narration_data)
        self.assertTrue(subject.startswith("SAGE Causal Attribution Report"))

    def test_04_mime_message_creation(self):
        subject = "Test SAGE Report"
        text = "Plain text version with framing: " + EvidencePacket.RESEARCH_FRAMING
        html_content = "<p>HTML version</p>"
        msg = create_mime_message(subject, text, html_content, to_addrs=["test@sage.ai"])

        self.assertEqual(msg["Subject"], subject)
        self.assertEqual(msg["To"], "test@sage.ai")
        self.assertTrue(msg.is_multipart())
        payload = msg.get_payload()
        self.assertEqual(len(payload), 2)
        self.assertEqual(payload[0].get_content_type(), "text/plain")
        self.assertEqual(payload[1].get_content_type(), "text/html")

    def test_05_smtp_dry_run(self):
        receipt = send_report(
            subject="Dry Run Subject",
            text_content="Body text",
            html_content="<p>Body HTML</p>",
            dry_run=True,
        )
        self.assertEqual(receipt["status"], "DRY_RUN_SAVED")
        self.assertTrue(receipt["message_id"].endswith("@sage.internal>"))
        self.assertIn("timestamp", receipt)

    def test_06_scheduler_on_demand_and_cron(self):
        receipt = generate_and_dispatch_report(dry_run=True)
        self.assertEqual(receipt["status"], "DRY_RUN_SAVED")

        sched = setup_scheduler(cron_day_of_week="fri", cron_hour=17, cron_minute=30, blocking=False, dry_run=True)
        job = sched.get_job("sage_weekly_attribution_report")
        self.assertIsNotNone(job)
        self.assertEqual(job.name, "SAGE Weekly Causal Attribution Report Dispatch")


if __name__ == "__main__":
    unittest.main()
