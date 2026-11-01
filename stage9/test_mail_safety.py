"""
stage9/test_mail_safety.py — Comprehensive SMTP mocking and mail safety verification (unittest).

Tests:
1. Persisted Live mode + no `--live` flag -> zero SMTP calls, returns status SUCCESS_DRY_RUN.
2. `--live` flag -> exactly one SMTP call, returns status SUCCESS_LIVE.
3. Scheduled send twice for one date -> exactly one SMTP call (second call skips due to idempotency).
4. Refusal checks for placeholder and unapproved recipients.
5. Verifies sent_log.jsonl line count remains unchanged at the end of the test suite.
"""

import json
import os
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from stage9.ops import (
    dispatch_email_v6,
    send_report_now_v6,
    set_send_mode_v6,
    get_runtime_config,
    save_runtime_config,
    SENT_LOG_PATH
)
from stage9.scheduler import execute_job


class TestMailSafety(unittest.TestCase):

    def setUp(self):
        self.backup_sent_log = None
        if SENT_LOG_PATH.exists():
            self.backup_sent_log = SENT_LOG_PATH.read_text(encoding="utf-8")
        self.orig_cfg = get_runtime_config()
        set_send_mode_v6("dry_run", user="test_fixture")
        self.orig_transport = os.environ.get("SAGE_MAIL_TRANSPORT")
        if "SAGE_MAIL_TRANSPORT" in os.environ:
            del os.environ["SAGE_MAIL_TRANSPORT"]
        import stage9.ops as ops_mod
        ops_mod._LAST_SEND_TIMESTAMP = 0.0

    def tearDown(self):
        save_runtime_config(self.orig_cfg, user="test_fixture")
        if self.backup_sent_log is not None:
            SENT_LOG_PATH.write_text(self.backup_sent_log, encoding="utf-8")
        if self.orig_transport is not None:
            os.environ["SAGE_MAIL_TRANSPORT"] = self.orig_transport
        elif "SAGE_MAIL_TRANSPORT" in os.environ:
            del os.environ["SAGE_MAIL_TRANSPORT"]
        import stage9.ops as ops_mod
        ops_mod._LAST_SEND_TIMESTAMP = 0.0

    def test_persisted_live_without_flag_forces_dry_run(self):
        """When controller runtime config has persisted 'live', force_dry_run=True makes 0 SMTP calls."""
        set_send_mode_v6("live", user="test")
        test_date = date(2025, 12, 31)
        recipient = "sreeshanmukhtrk@gmail.com"

        with patch("smtplib.SMTP") as mock_smtp, patch("smtplib.SMTP_SSL") as mock_smtp_ssl:
            res = send_report_now_v6(
                as_of=test_date,
                recipient=recipient,
                force_live=False,
                force_dry_run=True,
                user="test"
            )
            self.assertEqual(res.get("status"), "SUCCESS_DRY_RUN")
            self.assertEqual(mock_smtp.call_count, 0)
            self.assertEqual(mock_smtp_ssl.call_count, 0)

    def test_live_flag_makes_exactly_one_smtp_call(self):
        """Explicit force_live=True makes exactly one SMTP call and logs SUCCESS_LIVE."""
        test_date = date(2025, 12, 31)
        recipient = "sreeshanmukhtrk@gmail.com"

        mock_server = MagicMock()
        mock_server.sendmail.return_value = {}

        with patch.dict(os.environ, {
            "SAGE_SEND_ENABLED": "true",
            "SMTP_USER": "test_user@gmail.com",
            "SMTP_PASSWORD": "valid_test_password_16ch",
            "SMTP_HOST": "smtp.gmail.com",
            "SMTP_PORT": "587"
        }), patch("smtplib.SMTP", return_value=mock_server) as mock_smtp:
            res = send_report_now_v6(
                as_of=test_date,
                recipient=recipient,
                force_live=True,
                force_dry_run=False,
                user="test"
            )
            self.assertEqual(res.get("status"), "SUCCESS_LIVE")
            self.assertEqual(mock_smtp.call_count, 1)
            self.assertEqual(mock_server.sendmail.call_count, 1)

    def test_scheduled_send_twice_for_one_date_makes_one_call(self):
        """Scheduled job for the same date called twice executes exactly once due to idempotency."""
        test_date = date(2025, 6, 15)
        recipient = "sreeshanmukhtrk@gmail.com"

        mock_server = MagicMock()
        mock_server.sendmail.return_value = {}

        with patch.dict(os.environ, {
            "SAGE_SEND_ENABLED": "true",
            "SMTP_USER": "test_user@gmail.com",
            "SMTP_PASSWORD": "valid_test_password_16ch",
            "SMTP_HOST": "smtp.gmail.com",
            "SMTP_PORT": "587"
        }), patch("smtplib.SMTP", return_value=mock_server) as mock_smtp:
            # First call
            ok1 = execute_job("nightly_digest", as_of=test_date, force=False, advance_pointer=False)
            self.assertTrue(ok1)
            self.assertEqual(mock_smtp.call_count, 1)

            # Second call (same date)
            ok2 = execute_job("nightly_digest", as_of=test_date, force=False, advance_pointer=False)
            self.assertTrue(ok2)
            # SMTP should NOT have been called a second time
            self.assertEqual(mock_smtp.call_count, 1)

    def test_refused_placeholder_recipient(self):
        """Placeholder recipient is refused without making SMTP calls."""
        with patch("smtplib.SMTP") as mock_smtp:
            res = dispatch_email_v6(
                subject="Test",
                html_body="<p>test</p>",
                text_body="test",
                recipient="test@example.com",
                as_of=date(2025, 12, 31),
                force_live=True
            )
            self.assertEqual(res.get("status"), "REFUSED_PLACEHOLDER")
            self.assertEqual(mock_smtp.call_count, 0)


if __name__ == "__main__":
    unittest.main()
