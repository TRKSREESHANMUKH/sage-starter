"""
Tests for Controller Dark Theme and Hero Status Card (Part C4).
"""

import unittest
from pathlib import Path
from starlette.requests import Request
from controller.app import _base_ctx


class TestControllerDarkTheme(unittest.TestCase):

    def test_dark_palette_in_templates(self):
        root = Path("controller/templates")
        for filename in ["dashboard.html", "schedule.html", "login.html"]:
            content = (root / filename).read_text(encoding="utf-8")
            self.assertIn("#0b0f19", content, f"{filename} missing #0b0f19 bg")
            self.assertIn("#131b2e", content, f"{filename} missing #131b2e surface")
            self.assertIn("#1e293b", content, f"{filename} missing #1e293b border")
            self.assertIn("#f8fafc", content, f"{filename} missing #f8fafc text")
            self.assertIn("#94a3b8", content, f"{filename} missing #94a3b8 muted")
            self.assertIn("#3b82f6", content, f"{filename} missing #3b82f6 accent")

    def test_hero_status_card_in_dashboard(self):
        dash_content = Path("controller/templates/dashboard.html").read_text(encoding="utf-8")
        self.assertIn("hero-card", dash_content)
        self.assertIn("hero.day_label", dash_content)
        self.assertIn("hero.status_label", dash_content)
        self.assertIn("hero.status_color", dash_content)
        self.assertIn("Active Backorders", dash_content)
        self.assertIn("Weakest Material", dash_content)
        self.assertIn("Queue Position", dash_content)
        self.assertIn("sage_logo_card.png", dash_content)

    def test_hero_context_data(self):
        # Mock request and session
        scope = {"type": "http", "method": "GET", "path": "/ctrl/"}
        req = Request(scope)
        sess = {"csrf": "test_csrf", "user": "test_user"}
        ctx = _base_ctx(req, sess)
        self.assertIn("hero", ctx)
        hero = ctx["hero"]
        self.assertIn("status_label", hero)
        self.assertIn(hero["status_label"], ["CALM", "WATCH", "ALERT"])
        self.assertIn("status_color", hero)
        self.assertIn("day_label", hero)
        self.assertIn("backorder_val", hero)
        self.assertIn("weakest_material_val", hero)
        self.assertIn("queue_val", hero)


if __name__ == "__main__":
    unittest.main()
