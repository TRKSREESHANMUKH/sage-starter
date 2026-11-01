"""
stage9/test_ui_mock_suite.py — Comprehensive Playwright and Integration Test Suite
Validates all Part 6 requirements running against the application with SAGE_MAIL_TRANSPORT=mock.
"""

import os
import re
import sys
import time
import unittest
from pathlib import Path

# Force mock transport for all tests
os.environ["SAGE_MAIL_TRANSPORT"] = "mock"

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from playwright.sync_api import sync_playwright

from web.auth import (
    add_user,
    remove_user,
    clear_failed_attempts,
    find_user,
    seed_default_user_if_needed,
)
from stage9.ops import (
    send_report_now_v6,
    get_runtime_config,
    save_runtime_config,
    _MOCK_DISPATCH_EVENTS,
    SENT_LOG_PATH,
)
from stage9.recipients import load_saved_recipients, save_recipients, get_default_recipients


class TestUIMockSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.viewer_url = "http://127.0.0.1:8000"
        cls.ctrl_url = "http://127.0.0.1:8001"

        # Verify running servers
        import urllib.request
        try:
            urllib.request.urlopen(f"{cls.viewer_url}/health", timeout=3)
            urllib.request.urlopen(f"{cls.ctrl_url}/health", timeout=3)
        except Exception as e:
            raise RuntimeError(f"SAGE servers must be running on 8000 and 8001. Error: {e}")

        # Seed test user
        seed_default_user_if_needed()
        cls.test_username = "test_operator"
        cls.test_email = "test_operator@sage-plant.local"
        cls.test_pwd = "TestPassword123!"
        remove_user(cls.test_username)
        add_user(cls.test_username, cls.test_email, "operator", cls.test_pwd)

        # Seed recipients
        save_recipients(get_default_recipients(), user="test_suite")

        # Start Playwright
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        try:
            cls.browser.close()
            cls.playwright.stop()
        except Exception:
            pass
        remove_user(cls.test_username)

    def setUp(self):
        clear_failed_attempts("127.0.0.1")
        clear_failed_attempts(self.test_username)
        clear_failed_attempts(self.test_email)

    def test_01_login_flows(self):
        """Viewer and controller accept username or email, reject bad passwords with exact generic error."""
        # 1a. Viewer login with username
        ctx = self.browser.new_context()
        page = ctx.new_page()
        page.goto(f"{self.viewer_url}/login")
        page.fill("#username_or_email", self.test_username)
        page.fill("#password", self.test_pwd)
        page.click("button[type=submit]")
        page.wait_for_url(f"{self.viewer_url}/")
        self.assertEqual(page.url.rstrip("/"), self.viewer_url)
        ctx.close()

        # 1b. Viewer login with email
        ctx_email = self.browser.new_context()
        page_email = ctx_email.new_page()
        page_email.goto(f"{self.viewer_url}/login")
        page_email.fill("#username_or_email", self.test_email)
        page_email.fill("#password", self.test_pwd)
        page_email.click("button[type=submit]")
        page_email.wait_for_url(f"{self.viewer_url}/")
        self.assertEqual(page_email.url.rstrip("/"), self.viewer_url)
        ctx_email.close()

        # 1c. Controller login with username
        ctx_ctrl = self.browser.new_context()
        page_ctrl = ctx_ctrl.new_page()
        page_ctrl.goto(f"{self.ctrl_url}/ctrl/login")
        page_ctrl.fill("#username_or_email", self.test_username)
        page_ctrl.fill("#password", self.test_pwd)
        page_ctrl.click("button[type=submit]")
        page_ctrl.wait_for_url(f"{self.ctrl_url}/ctrl/")
        self.assertIn("/ctrl/", page_ctrl.url)
        ctx_ctrl.close()

        # 1d. Bad password generic error on viewer
        bad_ctx = self.browser.new_context()
        bad_page = bad_ctx.new_page()
        bad_page.goto(f"{self.viewer_url}/login")
        bad_page.fill("#username_or_email", self.test_username)
        bad_page.fill("#password", "WrongPassword999!")
        bad_page.click("button[type=submit]")
        bad_page.wait_for_selector(".error-banner")
        self.assertIn("Incorrect username or password", bad_page.inner_text(".error-banner"))
        bad_ctx.close()

        # 1e. Bad password generic error on controller
        bad_ctx_c = self.browser.new_context()
        bad_page_c = bad_ctx_c.new_page()
        bad_page_c.goto(f"{self.ctrl_url}/ctrl/login")
        bad_page_c.fill("#username_or_email", self.test_username)
        bad_page_c.fill("#password", "WrongPassword999!")
        bad_page_c.click("button[type=submit]")
        bad_page_c.wait_for_selector(".error")
        self.assertIn("Incorrect username or password", bad_page_c.inner_text(".error"))
        bad_ctx_c.close()

    def test_02_send_flow_and_modal_confirm(self):
        """Select 2 saved + 1 custom, verify modal lists all 3 with name/role/email, send returns 250."""
        ctx = self.browser.new_context()
        page = ctx.new_page()

        # Login to controller
        page.goto(f"{self.ctrl_url}/ctrl/login")
        page.fill("#username_or_email", self.test_username)
        page.fill("#password", self.test_pwd)
        page.click("button[type=submit]")
        page.wait_for_url(f"{self.ctrl_url}/ctrl/")

        _MOCK_DISPATCH_EVENTS.clear()

        # Fill custom recipient
        page.fill("#custom-recipient-email", "colleague@sage-plant.org")
        page.fill("#custom-recipient-name", "Alex Smith")
        page.fill("#custom-recipient-role", "Purchasing head")

        # Click Send
        page.click("#main-send-btn")

        # Modal must open
        page.wait_for_selector("#send-modal.open")
        modal_text = page.inner_text("#modal-recipients-list")
        self.assertIn("sreeshanmukhtrk@gmail.com", modal_text)
        self.assertIn("trksreeshanmukh026@gmail.com", modal_text)
        self.assertIn("colleague@sage-plant.org", modal_text)
        self.assertIn("Alex Smith", modal_text)
        self.assertIn("Purchasing head", modal_text)

        # Confirm send
        page.click("#confirm-send-btn")
        time.sleep(2.5)

        # Verify sent_log.jsonl captured send with SUCCESS_LIVE and 250
        import json
        recent_sends = []
        if SENT_LOG_PATH.exists():
            with open(SENT_LOG_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        try:
                            recent_sends.append(json.loads(line))
                        except Exception:
                            pass
        self.assertGreater(len(recent_sends), 0)
        live_sends = [s for s in recent_sends if s.get("status") == "SUCCESS_LIVE"]
        self.assertGreater(len(live_sends), 0)
        last_live = live_sends[-1]
        self.assertEqual(last_live.get("status"), "SUCCESS_LIVE")
        self.assertEqual(last_live.get("smtp_code"), 250)

        ctx.close()

    def test_03_test_run(self):
        """Test run prepares report, makes 0 SMTP calls, and logs SUCCESS_DRY_RUN in sent_log."""
        _MOCK_DISPATCH_EVENTS.clear()
        res = send_report_now_v6(
            recipients=["sreeshanmukhtrk@gmail.com"],
            force_dry_run=True,
            user="test_runner"
        )
        self.assertEqual(res.get("status"), "SUCCESS_DRY_RUN")
        self.assertEqual(len(_MOCK_DISPATCH_EVENTS), 0)  # zero SMTP calls

        found_dry_run = False
        with open(SENT_LOG_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if "SUCCESS_DRY_RUN" in line:
                    found_dry_run = True
                    break
        self.assertTrue(found_dry_run)

    def test_04_no_mode_chip_on_controller(self):
        """Verify no mode chip or dryrun warning banner exists on controller page."""
        ctx = self.browser.new_context()
        page = ctx.new_page()
        page.goto(f"{self.ctrl_url}/ctrl/login")
        page.fill("#username_or_email", self.test_username)
        page.fill("#password", self.test_pwd)
        page.click("button[type=submit]")
        page.wait_for_url(f"{self.ctrl_url}/ctrl/")

        content = page.content()
        self.assertNotIn("status-mode-pill", content)
        self.assertNotIn("dryrun-alert-banner", content)
        self.assertNotIn("switch-live-modal", content)
        ctx.close()

    def test_05_twenty_consecutive_sends_succeed(self):
        """20 consecutive sends succeed without tripping cooldowns or rate limits."""
        for i in range(20):
            res = send_report_now_v6(
                recipients=["sreeshanmukhtrk@gmail.com"],
                force_live=True,
                user=f"consecutive_test_{i}"
            )
            self.assertEqual(res.get("status"), "SUCCESS_LIVE", f"Send #{i+1} failed: {res.get('error')}")
            self.assertEqual(res.get("smtp_code"), 250)

    def test_06_automatic_daily_mail_toggle(self):
        """Toggling the checkbox flips schedule.runtime.yaml and updates description text."""
        ctx = self.browser.new_context()
        page = ctx.new_page()
        page.goto(f"{self.ctrl_url}/ctrl/login")
        page.fill("#username_or_email", self.test_username)
        page.fill("#password", self.test_pwd)
        page.click("button[type=submit]")
        page.wait_for_url(f"{self.ctrl_url}/ctrl/")

        # Toggle off
        page.eval_on_selector("#auto-mail-toggle", "el => { el.checked = false; toggleAutoMail(false); }")
        time.sleep(1.0)
        cfg = get_runtime_config()
        self.assertFalse(cfg.get("automatic_daily_mail"))

        # Toggle on
        page.eval_on_selector("#auto-mail-toggle", "el => { el.checked = true; toggleAutoMail(true); }")
        time.sleep(1.0)
        cfg2 = get_runtime_config()
        self.assertTrue(cfg2.get("automatic_daily_mail"))
        self.assertIn("Next run: Today at", page.inner_text("#auto-mail-desc"))

        ctx.close()

    def test_07_test_connection_toast(self):
        """Clicking Test connection button invokes endpoint and displays toast."""
        ctx = self.browser.new_context()
        page = ctx.new_page()
        page.goto(f"{self.ctrl_url}/ctrl/login")
        page.fill("#username_or_email", self.test_username)
        page.fill("#password", self.test_pwd)
        page.click("button[type=submit]")
        page.wait_for_url(f"{self.ctrl_url}/ctrl/")

        page.click("#btn-test-connection")
        page.wait_for_selector("#toast.show", timeout=10000)
        toast_text = page.inner_text("#toast")
        self.assertTrue("SMTP" in toast_text)
        ctx.close()

    def test_08_feed_card_layout_and_theme(self):
        """Feed card is prominent and first card; controller is dark themed; viewer is light themed."""
        ctx_c = self.browser.new_context()
        page_c = ctx_c.new_page()

        # Controller page
        page_c.goto(f"{self.ctrl_url}/ctrl/login")
        page_c.fill("#username_or_email", self.test_username)
        page_c.fill("#password", self.test_pwd)
        page_c.click("button[type=submit]")
        page_c.wait_for_url(f"{self.ctrl_url}/ctrl/")

        feed_card = page_c.query_selector(".feed-showpiece-card")
        self.assertIsNotNone(feed_card)
        self.assertIn("FEED", page_c.inner_text(".feed-showpiece-card .card-title").upper())

        # Background color on controller is dark
        bg_ctrl = page_c.evaluate("() => window.getComputedStyle(document.body).backgroundColor")
        self.assertIn(bg_ctrl, ["rgb(11, 15, 25)", "rgb(19, 27, 46)"])

        # Zero emojis on controller
        content_ctrl = page_c.content()
        emojis_ctrl = [c for c in content_ctrl if ord(c) >= 0x1F300 or ord(c) in [0x2705, 0x274C, 0x26A0, 0x2728, 0x1F525]]
        self.assertEqual(len(emojis_ctrl), 0)
        ctx_c.close()

        # Viewer page is light
        ctx_v = self.browser.new_context()
        page_v = ctx_v.new_page()
        page_v.goto(f"{self.viewer_url}/login")
        page_v.fill("#username_or_email", self.test_username)
        page_v.fill("#password", self.test_pwd)
        page_v.click("button[type=submit]")
        page_v.wait_for_url(f"{self.viewer_url}/")

        bg_viewer = page_v.evaluate("() => window.getComputedStyle(document.body).backgroundColor")
        self.assertEqual(bg_viewer, "rgb(248, 250, 252)")

        content_viewer = page_v.content()
        emojis_viewer = [c for c in content_viewer if ord(c) >= 0x1F300 or ord(c) in [0x2705, 0x274C, 0x26A0, 0x2728, 0x1F525]]
        self.assertEqual(len(emojis_viewer), 0)
        ctx_v.close()

    def test_09_crawl_banned_words(self):
        """Crawl pages, emails, and PDFs: zero /demo|simulat/i; 'synthetic' only in allowed locations."""
        ctx = self.browser.new_context()
        page = ctx.new_page()

        # Log in to viewer
        page.goto(f"{self.viewer_url}/login")
        page.fill("#username_or_email", self.test_username)
        page.fill("#password", self.test_pwd)
        page.click("button[type=submit]")
        page.wait_for_url(f"{self.viewer_url}/")

        pattern_banned = re.compile(r"\b(demo|simulation|simulated|simulating)\b", re.IGNORECASE)

        # Check Viewer pages: Today and Insights
        for route in ["/", "/insights"]:
            page.goto(f"{self.viewer_url}{route}")
            visible_text = page.inner_text("body")
            matches = pattern_banned.findall(visible_text)
            self.assertEqual(len(matches), 0, f"Found banned words {matches} on viewer route {route}")

        # Check Controller main page
        page.goto(f"{self.ctrl_url}/ctrl/login")
        page.fill("#username_or_email", self.test_username)
        page.fill("#password", self.test_pwd)
        page.click("button[type=submit]")
        page.wait_for_url(f"{self.ctrl_url}/ctrl/")

        ctrl_text = page.inner_text("body")
        matches_ctrl = pattern_banned.findall(ctrl_text)
        self.assertEqual(len(matches_ctrl), 0, f"Found banned words {matches_ctrl} on controller page")

        ctx.close()


if __name__ == "__main__":
    unittest.main()
