"""
Tests for Controller Recipients, Emoji Removal, and Footer Framing (Part C1-C3).
"""

import unittest
import json
import re
from pathlib import Path
from stage9.recipients import (
    validate_recipient_email,
    load_saved_recipients,
    save_recipients,
    load_send_history,
    RECIPIENTS_FILE,
)


class TestControllerRecipients(unittest.TestCase):

    def setUp(self):
        self._orig_data = RECIPIENTS_FILE.read_bytes() if RECIPIENTS_FILE.exists() else None

    def tearDown(self):
        if self._orig_data is not None:
            RECIPIENTS_FILE.write_bytes(self._orig_data)

    def test_email_validation_valid(self):
        ok, clean, err = validate_recipient_email("admin@sage-ops.com")
        self.assertTrue(ok)
        self.assertEqual(clean, "admin@sage-ops.com")
        self.assertEqual(err, "")

    def test_email_validation_rejections(self):
        # Empty
        ok, _, err = validate_recipient_email("")
        self.assertFalse(ok)

        # Whitespace / newline injection
        ok, _, err = validate_recipient_email("bad@ops.com\nBcc: evil@hacker.com")
        self.assertFalse(ok)
        ok, _, err = validate_recipient_email("user1@a.com, user2@b.com")
        self.assertFalse(ok)

        # Disallowed placeholder/test domains
        disallowed = [
            "test@example.com",
            "mock@test.com",
            "dummy@placeholder.com",
            "user@internal.local"
        ]
        for em in disallowed:
            ok, _, err = validate_recipient_email(em)
            self.assertFalse(ok, f"Expected {em} to be rejected")

    def test_save_and_load_recipients(self):
        test_contacts = [
            {"email": "ops1@sage-ops.com", "name": "Ops Lead", "role": "Lead", "active": True},
            {"email": "ops2@sage-ops.com", "name": "Supply VP", "role": "VP", "active": False},
        ]
        ok, msg = save_recipients(test_contacts)
        self.assertTrue(ok)

        loaded = load_saved_recipients()
        self.assertEqual(len(loaded), 2)
        self.assertEqual(loaded[0]["email"], "ops1@sage-ops.com")
        self.assertTrue(loaded[0]["active"])
        self.assertEqual(loaded[1]["email"], "ops2@sage-ops.com")
        self.assertFalse(loaded[1]["active"])

        # Multiple recipients (no 3-slot cap)
        more_contacts = [
            {"email": f"user{i}@sage-ops.com", "name": f"Staff Member", "role": "Staff", "active": True}
            for i in range(4)
        ]
        ok, msg = save_recipients(more_contacts)
        self.assertTrue(ok)
        self.assertEqual(len(load_saved_recipients()), 4)

    def test_send_history(self):
        history = load_send_history(limit=5)
        self.assertIsInstance(history, list)
        self.assertLessEqual(len(history), 5)
        if history:
            item = history[0]
            self.assertIn("recipient", item)
            self.assertIn("status", item)
            self.assertIn("timestamp", item)
            self.assertIn("digest_date", item)

    def test_no_emojis_in_controller(self):
        emoji_pattern = re.compile(r'[\U00010000-\U0010ffff]|[\u2600-\u27bf]|[\u2300-\u23ff]|[\u2b50-\u2b55]')
        root = Path(__file__).resolve().parent.parent / "controller"
        for tpl in root.glob("templates/*.html"):
            content = tpl.read_text(encoding="utf-8")
            matches = emoji_pattern.findall(content)
            self.assertEqual(len(matches), 0, f"Found emojis in {tpl.name}: {matches}")

        app_content = (root / "app.py").read_text(encoding="utf-8")
        matches = emoji_pattern.findall(app_content)
        self.assertEqual(len(matches), 0, f"Found emojis in controller/app.py: {matches}")

    def test_framing_in_dashboard(self):
        framing = "SAGE performs controlled synthetic causal-attribution evaluation under an expert-defined causal model; it does not claim to prove real-world causality."
        dashboard = Path(__file__).resolve().parent.parent / "controller" / "templates" / "dashboard.html"
        self.assertIn(framing, dashboard.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
