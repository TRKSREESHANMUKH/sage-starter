"""
stage9/test_mock_transport.py — Guard tests for SAGE mock email transport.
Guarantees that tests and verify_all never reach real smtplib.
"""

import os
import unittest
from unittest.mock import patch
from datetime import date
from stage9.ops import dispatch_email_v6, send_report_now_v6


class TestMockTransportGuard(unittest.TestCase):

    def setUp(self):
        self._orig_transport = os.environ.get("SAGE_MAIL_TRANSPORT")
        os.environ["SAGE_MAIL_TRANSPORT"] = "mock"

    def tearDown(self):
        if self._orig_transport is not None:
            os.environ["SAGE_MAIL_TRANSPORT"] = self._orig_transport
        else:
            os.environ.pop("SAGE_MAIL_TRANSPORT", None)

    def test_mock_transport_intercepts_smtp(self):
        """Confirms smtplib.SMTP is never called when SAGE_MAIL_TRANSPORT=mock."""
        with patch("smtplib.SMTP") as mock_smtp, patch("smtplib.SMTP_SSL") as mock_ssl:
            res = dispatch_email_v6(
                subject="Test Mock",
                html_body="<p>Test</p>",
                text_body="Test",
                recipients=["sreeshanmukhtrk@gmail.com"],
                force_live=True
            )
            # smtplib MUST NOT be called
            mock_smtp.assert_not_called()
            mock_ssl.assert_not_called()

            self.assertEqual(res.get("status"), "SUCCESS_LIVE")
            self.assertEqual(res.get("transport"), "mock")
            self.assertEqual(res.get("smtp_code"), 250)

    def test_max_five_recipients_enforced(self):
        """Verifies at most 5 recipients per click."""
        recs = [f"user{i}@company.com" for i in range(6)]
        res = dispatch_email_v6(
            subject="Test",
            html_body="<p>Test</p>",
            text_body="Test",
            recipients=recs,
            force_live=True
        )
        self.assertEqual(res.get("status"), "REFUSED_INVALID")
        self.assertIn("Maximum 5", res.get("error", ""))

    def test_twenty_consecutive_sends_succeed(self):
        """Confirms send caps (10/hr, 30/day) and cool-downs are removed."""
        for i in range(20):
            res = dispatch_email_v6(
                subject=f"Bulk Send {i}",
                html_body=f"<p>Message {i}</p>",
                text_body=f"Message {i}",
                recipients=["sreeshanmukhtrk@gmail.com"],
                force_live=True
            )
            self.assertEqual(res.get("status"), "SUCCESS_LIVE", f"Failed on send #{i}: {res}")


if __name__ == "__main__":
    unittest.main()
