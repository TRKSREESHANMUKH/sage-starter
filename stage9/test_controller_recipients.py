"""
stage9/test_controller_recipients.py — Verification of Manual Send Recipients, Rate Limiting & Mock SMTP Dispatch.

Part D Specifications:
- D1: Manual recipients strict validation (RFC regex + parseaddr, reject whitespace/newlines/commas/semicolons, max 3, lowercase).
- D1: Recent recipients dropdown persisted in stage9/state/recent_recipients.json (max 5, never in .env), remove button.
- D2: Safety: scheduled mail unaffected; rate limit: max 10 real sends/hr, 30/day; live sends require Live mode.
- D3: Tests with mock SMTP only:
  - invalid/injection strings rejected
  - 4th recipient rejected
  - Dry-run adds log entry with NO SMTP call
  - Live path makes exactly ONE mocked SMTP call per recipient group
  - Rate limit enforced
  - Scheduled mail unaffected
  - Real SMTP calls from tests MUST BE 0; live sends in stage9/state/sent_log.jsonl must stay strictly 3.
"""

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock

ROOT_DIR = Path(__file__).resolve().parent.parent

from stage9.ops import (
    validate_manual_recipient,
    validate_manual_recipients,
    get_recent_recipients,
    save_recent_recipient,
    remove_recent_recipient,
    check_live_send_rate_limits,
    dispatch_email_v6,
    send_report_now_v6,
    RECENT_RECIPIENTS_PATH,
    SENT_LOG_PATH,
)


class TestControllerRecipients(unittest.TestCase):

    def setUp(self):
        # Backup recent recipients file if exists
        self.backup_recent = None
        if RECENT_RECIPIENTS_PATH.exists():
            self.backup_recent = RECENT_RECIPIENTS_PATH.read_text(encoding="utf-8")

    def tearDown(self):
        # Restore recent recipients file
        if self.backup_recent is not None:
            RECENT_RECIPIENTS_PATH.write_text(self.backup_recent, encoding="utf-8")
        elif RECENT_RECIPIENTS_PATH.exists():
            RECENT_RECIPIENTS_PATH.unlink()

    def test_invalid_and_injection_strings_rejected(self):
        """D1 & D3: Invalid and injection strings must be strictly rejected."""
        invalid_cases = [
            "mentor\n@university.edu",
            "mentor\r@university.edu",
            "mentor\t@university.edu",
            "mentor @university.edu",
            "mentor;bcc@bad.com",
            "mentor,second@bad.com",
            "not-an-email",
            "@missing-local.com",
            "missing-domain@",
            "user@domain",
            "user@.com",
            "user@localhost.local",
            "user@system@bad.com",
        ]
        for bad in invalid_cases:
            ok, clean, err = validate_manual_recipient(bad)
            self.assertFalse(ok, f"Expected failure for '{bad}' but got ok=True")
            self.assertNotEqual(err, "")

    def test_valid_manual_recipients(self):
        """D1: Valid email addresses are accepted and lowercased."""
        valid_cases = [
            ("Mentor@University.EDU", "mentor@university.edu"),
            ("prof.smith+sage@college.org", "prof.smith+sage@college.org"),
            ("faculty_eval@univ-net.edu", "faculty_eval@univ-net.edu"),
        ]
        for raw, expected in valid_cases:
            ok, clean, err = validate_manual_recipient(raw)
            self.assertTrue(ok, f"Expected success for '{raw}': {err}")
            self.assertEqual(clean, expected)

    def test_fourth_recipient_rejected(self):
        """D1 & D3: Maximum 3 recipients allowed per send; 4th recipient rejected."""
        four_recs = ["a@univ.edu", "b@univ.edu", "c@univ.edu", "d@univ.edu"]
        ok, clean_list, err = validate_manual_recipients(four_recs)
        self.assertFalse(ok)
        self.assertIn("4th recipient rejected", err)

        three_recs = ["a@univ.edu", "b@univ.edu", "c@univ.edu"]
        ok, clean_list, err = validate_manual_recipients(three_recs)
        self.assertTrue(ok)
        self.assertEqual(len(clean_list), 3)

    def test_recent_recipients_persistence(self):
        """D1: Recent recipients stored in stage9/state, max 5, deduplicated."""
        # Clean state for test
        if RECENT_RECIPIENTS_PATH.exists():
            RECENT_RECIPIENTS_PATH.unlink()

        save_recent_recipient("mentor1@univ.edu")
        save_recent_recipient("mentor2@univ.edu")
        save_recent_recipient("mentor3@univ.edu")
        save_recent_recipient("mentor4@univ.edu")
        save_recent_recipient("mentor5@univ.edu")
        save_recent_recipient("mentor6@univ.edu")

        recent = get_recent_recipients()
        self.assertEqual(len(recent), 5)
        self.assertEqual(recent[0], "mentor6@univ.edu")
        self.assertNotIn("mentor1@univ.edu", recent)  # Oldest dropped

        # Test deduplication
        save_recent_recipient("mentor3@univ.edu")
        recent = get_recent_recipients()
        self.assertEqual(len(recent), 5)
        self.assertEqual(recent[0], "mentor3@univ.edu")

        # Test remove
        remove_recent_recipient("mentor3@univ.edu")
        recent = get_recent_recipients()
        self.assertEqual(len(recent), 4)
        self.assertNotIn("mentor3@univ.edu", recent)

    @patch("smtplib.SMTP")
    @patch("smtplib.SMTP_SSL")
    def test_dry_run_adds_log_entry_with_no_smtp_call(self, mock_ssl, mock_smtp):
        """D3: Dry-run adds log entry with zero SMTP calls."""
        res = dispatch_email_v6(
            subject="Test Subject",
            html_body="<p>Test</p>",
            text_body="Test",
            recipient="mentor@univ.edu",
            force_dry_run=True,
            mode="manual"
        )
        self.assertEqual(res["status"], "SUCCESS_DRY_RUN")
        mock_smtp.assert_not_called()
        mock_ssl.assert_not_called()

    @patch("smtplib.SMTP")
    def test_live_path_makes_exactly_one_mocked_smtp_call(self, mock_smtp_cls):
        """D3: Live path makes exactly ONE mocked SMTP call per recipient group."""
        mock_server = MagicMock()
        mock_smtp_cls.return_value = mock_server

        targets = ["mentor1@univ.edu", "mentor2@univ.edu"]

        with patch("stage9.ops.check_and_update_send_rate_limit", return_value=(True, "")):
            with patch("stage9.ops.check_live_send_rate_limits", return_value=(True, "")):
                with patch("stage9.ops.log_sent_event_v6") as mock_log:
                    mock_log.return_value = {"timestamp": "2026-10-31T12:00:00Z"}
                    with patch.dict(os.environ, {"SMTP_USER": "test@gmail.com", "SMTP_PASSWORD": "valid_16_char_pwd"}):
                        res = dispatch_email_v6(
                            subject="Test Subject",
                            html_body="<p>Test</p>",
                            text_body="Test",
                            recipients=targets,
                            force_live=True,
                            mode="manual"
                        )
                        self.assertEqual(res["status"], "SUCCESS_LIVE")
                        # Exactly ONE sendmail call for the recipient group
                        mock_server.sendmail.assert_called_once()
                        call_args = mock_server.sendmail.call_args[0]
                        self.assertEqual(call_args[0], "test@gmail.com")
                        self.assertEqual(call_args[1], targets)

    def test_live_rate_limit_enforced(self):
        """D2 & D3: Rate limit max 10/hr and 30/day enforced with clear message."""
        with tempfile.NamedTemporaryFile("w+", delete=False) as tf:
            tf_path = Path(tf.name)
            # Write 10 recent SUCCESS_LIVE events within the last 5 minutes
            from datetime import datetime, timezone
            now_iso = datetime.now(timezone.utc).isoformat()
            for i in range(10):
                tf.write(json.dumps({
                    "timestamp": now_iso,
                    "status": "SUCCESS_LIVE",
                    "recipient": f"user{i}@univ.edu"
                }) + "\n")
            tf.flush()

        try:
            with patch("stage9.ops.SENT_LOG_PATH", tf_path):
                ok, err = check_live_send_rate_limits()
                self.assertFalse(ok)
                self.assertIn("maximum 10 live sends per hour", err)
        finally:
            tf_path.unlink()

    def test_scheduled_mail_unaffected(self):
        """D2 & D3: Scheduled mail mode only accepts configured allowlist recipients."""
        # Non-allowlisted recipient in scheduled mode is refused
        res = dispatch_email_v6(
            subject="Nightly Digest",
            html_body="<p>Test</p>",
            text_body="Test",
            recipient="unknown_stranger@random.org",
            mode="scheduled",
            force_dry_run=True
        )
        self.assertEqual(res["status"], "REFUSED_PLACEHOLDER")


if __name__ == "__main__":
    unittest.main()
