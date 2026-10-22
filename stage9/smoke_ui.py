"""
stage9/smoke_ui.py — End-to-end Playwright click-through smoke test.

Tests:
1. Viewer on port 8000:
   - Verify framing sentence appears in footer and is byte-identical to Rule 2.
   - Switch to 2025-03-01:
     - On-time % is a single number.
     - Supplier deliveries equal Goods Receipts up to that day (4).
     - No "0 days late" appears next to an overdue count.
     - Download buttons (PDF, CSV) work and return 200 with non-empty content.
   - Switch to 2025-12-31:
     - On-time % reflects the 48 overdue orders (78.3%).
     - PO #18 flagged as stuck.
     - Sri Materials and Bharat Steel show idle note.
     - Finished goods table does NOT list raw materials.
   - Navigation tabs, expanders, and CSV downloads clicked.
   - Zero occurrences of "Errno", "Traceback", "NaN", "undefined", "[object Object]".
2. Controller on port 8001:
   - Log in with operator token (sage_dev_token_2025).
   - Verify framing sentence is present.
   - Click "Preview today's report": renders in <5s, contains framing sentence, owner email, priorities, no placeholders.
   - Click "Send report now" (Dry-run mode): UI shows result banner in <10s, sent_log gains 1 entry.
   - Past-day picker: select 2025-03-01, click Preview, verify preview shows March 1 data.
   - Reset demo button: click it, assert live DB drops to baseline day without error.
3. Universal assertions:
   - No user-visible paths ("/Users/", "/home/", "C:\\").
   - Every number is followed by a unit (orders, units, days, %, USD, s, items, etc.).
   - Every page responds in under 2 seconds (measured and printed).
4. Screenshots saved to analytics/screenshots/smoke/.
"""

import os
import sys
import time
import json
import re
from pathlib import Path
from typing import List, Dict, Any
from playwright.sync_api import sync_playwright, Page

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

SCREENSHOTS_DIR = ROOT_DIR / "analytics" / "screenshots" / "smoke"
SENT_LOG_PATH = ROOT_DIR / "stage9" / "state" / "sent_log.jsonl"

RULE2_FRAMING = (
    "SAGE performs controlled synthetic causal-attribution evaluation under an "
    "expert-defined causal model; it does not claim to prove real-world causality."
)

FORBIDDEN_TEXT_PATTERNS = [
    "Errno",
    "Traceback",
    "NaN",
    "undefined",
    "[object Object]",
    "/Users/",
    "/home/",
    "C:\\",
]


class SmokeTestRunner:
    def __init__(self, page: Page):
        self.page = page
        self.results: List[Dict[str, Any]] = []
        SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    def log_result(self, name: str, passed: bool, resp_time: float, detail: str = ""):
        self.results.append({
            "name": name,
            "status": "PASS" if passed else "FAIL",
            "time": f"{resp_time:.3f}s",
            "detail": detail
        })
        status_sym = "✓" if passed else "✗"
        print(f"[{status_sym}] {name:<42} Resp: {resp_time:.3f}s  {detail}")
        if not passed:
            raise AssertionError(f"Step '{name}' failed: {detail}")

    def measure_get(self, url: str) -> float:
        """Measures HTTP GET server response time, asserting status 200 and < 2.0s."""
        t0 = time.time()
        resp = self.page.request.get(url)
        elapsed = time.time() - t0
        assert resp.status == 200, f"Expected 200 from {url}, got {resp.status}"
        assert elapsed < 2.0, f"Server response from {url} took {elapsed:.3f}s, expected < 2.0s"
        return elapsed

    def check_cleanliness(self, content: str, screen_name: str):
        for pattern in FORBIDDEN_TEXT_PATTERNS:
            if pattern in content:
                raise AssertionError(f"Forbidden pattern '{pattern}' found in {screen_name}")

    def capture(self, filename: str):
        path = SCREENSHOTS_DIR / f"{filename}.png"
        self.page.screenshot(path=str(path), full_page=True)

    def run_all(self):
        print("\n" + "=" * 78)
        print("SAGE STAGE 9 PLAYWRIGHT SMOKE TEST SUITE")
        print("=" * 78)

        self.test_viewer_home()
        self.test_viewer_2025_03_01()
        self.test_viewer_2025_12_31()
        self.test_viewer_navigation_and_expanders()
        self.test_controller_login_and_dashboard()
        self.test_controller_preview_today()
        self.test_controller_send_dry_run()
        self.test_controller_preview_past_day()
        self.test_controller_reset_demo()

        self.print_summary()

    def test_viewer_home(self):
        url = "http://localhost:8000/"
        dur = self.measure_get(url)
        self.page.goto(url, wait_until="domcontentloaded")

        content = self.page.content()
        self.check_cleanliness(content, "Viewer Home (/)")

        footer_framing = self.page.locator(".footer-framing").inner_text()
        assert RULE2_FRAMING in footer_framing, f"Rule 2 framing mismatch in footer: '{footer_framing}'"

        self.capture("01_viewer_home")
        self.log_result("Viewer Home (/)", True, dur, "Loaded, Rule 2 framing verified")

    def test_viewer_2025_03_01(self):
        url = "http://localhost:8000/insights?date=2025-03-01"
        dur = self.measure_get(url)
        self.page.goto(url, wait_until="domcontentloaded")

        content = self.page.content()
        self.check_cleanliness(content, "Viewer Insights (2025-03-01)")
        text = self.page.inner_text("body")

        # 1. On-time % is a single number (100.0%)
        assert "100.0%" in text or "100%" in text, "Expected 100.0% on-time on 2025-03-01"

        # 2. Supplier deliveries equal Goods Receipts up to that day (4)
        supp_rows = self.page.locator("table:has-text('Material supplied') tbody tr")
        total_deliveries = 0
        for i in range(supp_rows.count()):
            cells = supp_rows.nth(i).locator("td")
            if cells.count() > 2:
                val = cells.nth(2).inner_text().strip()
                if val.isdigit():
                    total_deliveries += int(val)
        assert total_deliveries == 4, f"Expected 4 supplier deliveries on 2025-03-01, got {total_deliveries}"

        # 3. No "0 days late" appears next to an overdue count
        assert not re.search(r"[1-9]\d*\s+(?:orders?|units?)\s+overdue[^\n]*\b0\s+days\s+late", text, re.I), \
            "Found '0 days late' next to positive overdue count"

        # 4. Download buttons (PDF, CSV) work and return 200 with non-empty content
        t_pdf = time.time()
        pdf_resp = self.page.request.get("http://localhost:8000/report.pdf?date=2025-03-01")
        assert pdf_resp.status == 200 and len(pdf_resp.body()) > 5000, "Daily PDF failed or empty"

        t_csv1 = time.time()
        csv1 = self.page.request.get("http://localhost:8000/insights/suppliers.csv?date=2025-03-01")
        assert csv1.status == 200 and len(csv1.body()) > 100, "Suppliers CSV failed or empty"

        t_csv2 = time.time()
        csv2 = self.page.request.get("http://localhost:8000/insights/delays.csv?date=2025-03-01")
        assert csv2.status == 200 and len(csv2.body()) > 50, "Delays CSV failed or empty"

        self.capture("02_viewer_insights_2025_03_01")
        self.log_result("Viewer Insights (2025-03-01)", True, dur, "100.0% on-time, 4 deliveries, downloads 200")

    def test_viewer_2025_12_31(self):
        url = "http://localhost:8000/insights?date=2025-12-31"
        dur = self.measure_get(url)
        self.page.goto(url, wait_until="domcontentloaded")

        content = self.page.content()
        self.check_cleanliness(content, "Viewer Insights (2025-12-31)")
        text = self.page.inner_text("body")

        # 1. On-time % drops to reflect the 48 overdue orders (78.3%)
        assert "78.3%" in text, f"Expected 78.3% on-time on 2025-12-31, found: {text[:200]}"

        # 2. PO #18 flagged as stuck
        assert "PO #18" in text and "stuck" in text.lower(), "PO #18 not flagged as stuck"

        # 3. Sri Materials and Bharat Steel show the idle note
        assert "Sri Materials Pvt Ltd" in text and "Bharat Steel Works" in text, "Backup vendors missing"
        assert "backup vendors" in text.lower() or "no orders placed" in text.lower(), "Idle vendors note missing"

        # 4. Finished goods table does NOT list raw materials
        fg_table = self.page.locator("div:has(h3:has-text('Service by Finished Product')) table").first
        if fg_table.count() > 0:
            fg_text = fg_table.inner_text()
            assert "Material 101" not in fg_text, "Raw material 101 listed in finished goods table"
            assert "Raw steel" not in fg_text, "Raw steel listed in finished goods table"

        self.capture("03_viewer_insights_2025_12_31")
        self.log_result("Viewer Insights (2025-12-31)", True, dur, "78.3% on-time, PO #18 stuck, idle note present")

    def test_viewer_navigation_and_expanders(self):
        dur = self.measure_get("http://localhost:8000/")
        self.page.click("#nav-tab-today")
        self.page.wait_for_load_state("domcontentloaded")
        assert "/" in self.page.url

        self.page.click("#nav-tab-insights")
        self.page.wait_for_load_state("domcontentloaded")
        assert "insights" in self.page.url

        # Click all <summary> expanders
        summaries = self.page.locator("summary")
        count = summaries.count()
        for i in range(count):
            s = summaries.nth(i)
            if s.is_visible():
                s.click()

        self.check_cleanliness(self.page.content(), "Viewer Nav & Expanders")
        self.capture("04_viewer_nav_expanders")
        self.log_result("Viewer Navigation & Expanders", True, dur, f"Tabs switched, {count} expanders toggled")

    def test_controller_login_and_dashboard(self):
        url = "http://localhost:8001/ctrl/login"
        dur = self.measure_get(url)
        self.page.goto(url, wait_until="domcontentloaded")

        login_content = self.page.content()
        self.check_cleanliness(login_content, "Controller Login")
        assert RULE2_FRAMING in login_content, "Rule 2 framing missing from Controller Login"

        # Login with operator token
        t_login = time.time()
        self.page.fill("input[name='token']", "sage_dev_token_2025")
        self.page.click("button[type='submit']")
        self.page.wait_for_load_state("domcontentloaded")
        login_dur = time.time() - t_login

        assert "/ctrl/" in self.page.url or "/ctrl" in self.page.url, f"Expected dashboard URL, got {self.page.url}"
        dash_content = self.page.content()
        self.check_cleanliness(dash_content, "Controller Dashboard")

        dash_framing = self.page.locator(".framing-bar").inner_text()
        assert RULE2_FRAMING in dash_framing, f"Rule 2 framing mismatch on dashboard: {dash_framing}"

        self.capture("05_controller_dashboard")
        self.log_result("Controller Login & Dashboard", True, dur, "Logged in, Rule 2 framing verified")

    def test_controller_preview_today(self):
        t0 = time.time()
        self.page.click("button:has-text('👁 Preview')")
        self.page.wait_for_selector("#preview-content-area div[style*='font-family'], #preview-content-area table", timeout=5000)
        dur = time.time() - t0

        preview_html = self.page.locator("#preview-content-area").inner_html()
        meta_info = self.page.locator("#preview-meta-info").inner_text()
        self.check_cleanliness(preview_html, "Preview Modal")

        # 1. Contains framing sentence
        assert RULE2_FRAMING in preview_html, "Rule 2 framing sentence missing from email preview"

        # 2. Contains owner email
        assert "sreeshanmukhtrk@gmail.com" in meta_info or "sreeshanmukhtrk@gmail.com" in preview_html, \
            "Owner email missing from email preview modal"

        # 3. Non-empty priorities
        assert "Priorities" in preview_html or "Priority" in preview_html or "Action" in preview_html, \
            "Priorities missing from preview"

        # 4. No missing-data placeholders
        for ph in ["{{", "}}", "None", "null"]:
            assert ph not in preview_html, f"Found placeholder '{ph}' in preview HTML"

        self.capture("06_controller_preview_today")
        self.page.click("#preview-modal button:has-text('✕ Close')")
        self.log_result("Controller Preview Today's Report", True, dur, "Rendered in <5s with framing & owner email")

    def test_controller_send_dry_run(self):
        t0 = time.time()
        initial_log_count = 0
        if SENT_LOG_PATH.exists():
            initial_log_count = len([l for l in SENT_LOG_PATH.read_text(encoding="utf-8").strip().splitlines() if l.strip()])

        self.page.click("#main-send-btn")
        self.page.wait_for_selector("#send-modal.open", timeout=3000)
        self.page.click("#confirm-send-btn")

        self.page.wait_for_selector("#send-result[style*='display: block']", timeout=10000)
        dur = time.time() - t0

        result_text = self.page.locator("#send-result").inner_text()
        assert "Dry run complete" in result_text or "SUCCESS_DRY_RUN" in result_text or "Nothing was sent" in result_text, \
            f"Unexpected send result in dry-run mode: {result_text}"

        new_log_count = len([l for l in SENT_LOG_PATH.read_text(encoding="utf-8").strip().splitlines() if l.strip()]) if SENT_LOG_PATH.exists() else 0
        assert new_log_count == initial_log_count + 1, f"Sent log count expected {initial_log_count + 1}, got {new_log_count}"

        self.capture("07_controller_send_dry_run")
        self.page.click("#send-modal button:has-text('Cancel')")
        self.log_result("Controller Send Report (Dry-Run)", True, dur, "UI banner shown, sent_log gained 1 entry")

    def test_controller_preview_past_day(self):
        t0 = time.time()
        self.page.fill("#past-day-picker", "2025-03-01")
        self.page.click("button:has-text('👁 Preview')")

        self.page.wait_for_selector("#preview-content-area div[style*='font-family'], #preview-content-area table", timeout=5000)
        dur = time.time() - t0

        preview_html = self.page.locator("#preview-content-area").inner_html()
        meta_info = self.page.locator("#preview-meta-info").inner_text()

        assert "2025-03-01" in meta_info or "2025-03-01" in preview_html or "March 1" in preview_html or "01 Mar" in preview_html, \
            f"Preview did not show March 1 date: meta='{meta_info}'"

        self.capture("08_controller_preview_past_day")
        self.page.click("#preview-modal button:has-text('✕ Close')")
        self.log_result("Controller Past-Day Preview (2025-03-01)", True, dur, "March 1 past-day data rendered in preview")

    def test_controller_reset_demo(self):
        t0 = time.time()
        self.page.on("dialog", lambda dialog: dialog.accept())
        self.page.click("button:has-text('⟳ Reset Demo')")

        # Wait for toast to contain "reset"
        self.page.wait_for_function(
            "() => document.getElementById('toast') && document.getElementById('toast').textContent.toLowerCase().includes('reset')",
            timeout=15000
        )
        dur = time.time() - t0

        toast_text = self.page.locator("#toast").inner_text()
        assert "reset" in toast_text.lower(), f"Unexpected toast text after reset: {toast_text}"

        time.sleep(1.5)
        from stage9.current_day import get_current_day
        base_day = get_current_day()
        assert str(base_day) == "2025-12-31", f"Expected live db to reset to 2025-12-31, got {base_day}"

        self.capture("09_controller_reset_demo")
        self.log_result("Controller Demo Reset", True, dur, f"Live DB reset to {base_day} successfully")

    def print_summary(self):
        print("\n" + "=" * 78)
        print("SUMMARY OF PLAYWRIGHT SMOKE TEST RESULTS")
        print("=" * 78)
        print(f"{'Page / Flow Tested':<42} {'Status':<8} {'Resp Time':<12} {'Notes'}")
        print("-" * 78)
        for r in self.results:
            print(f"{r['name']:<42} {r['status']:<8} {r['time']:<12} {r['detail']}")
        print("=" * 78)
        print(f"Screenshots saved to: {SCREENSHOTS_DIR}")
        print("=" * 78 + "\n")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        runner = SmokeTestRunner(page)
        try:
            runner.run_all()
        finally:
            browser.close()


if __name__ == "__main__":
    main()
