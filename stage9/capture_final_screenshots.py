import os
import sys
import time
from playwright.sync_api import sync_playwright

def capture_all():
    os.makedirs("analytics/screenshots/final", exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # 1. Viewer login (light)
        page.goto("http://127.0.0.1:8000/login", wait_until="networkidle")
        page.screenshot(path="analytics/screenshots/final/01_viewer_login_light.png", full_page=True)
        print("Captured 01_viewer_login_light.png")

        # Login to viewer
        page.fill("#username_or_email", "supervisor")
        page.fill("#password", "operator_secret")
        page.click("button[type='submit']")
        page.wait_for_load_state("networkidle")

        # 6. Today page (light, no sage logo)
        page.goto("http://127.0.0.1:8000/", wait_until="networkidle")
        page.screenshot(path="analytics/screenshots/final/06_viewer_today_light.png", full_page=True)
        print("Captured 06_viewer_today_light.png")

        # 7. Insights page (light, no weekly trends)
        page.goto("http://127.0.0.1:8000/insights", wait_until="networkidle")
        page.screenshot(path="analytics/screenshots/final/07_viewer_insights_light.png", full_page=True)
        print("Captured 07_viewer_insights_light.png")

        # New context for controller
        ctrl_context = browser.new_context(viewport={"width": 1440, "height": 1080})
        ctrl_page = ctrl_context.new_page()

        # 2. Controller login (dark)
        ctrl_page.goto("http://127.0.0.1:8001/ctrl/login", wait_until="networkidle")
        ctrl_page.screenshot(path="analytics/screenshots/final/02_controller_login_dark.png", full_page=True)
        print("Captured 02_controller_login_dark.png")

        # Login to controller
        ctrl_page.fill("#username_or_email", "admin")
        ctrl_page.fill("#password", "operator_secret")
        ctrl_page.click("button[type='submit']")
        ctrl_page.wait_for_load_state("networkidle")

        # 3. Controller main (feed first, no mode chip)
        ctrl_page.goto("http://127.0.0.1:8001/ctrl/", wait_until="networkidle")
        ctrl_page.screenshot(path="analytics/screenshots/final/03_controller_main_feed_first.png")
        print("Captured 03_controller_main_feed_first.png")

        # 4. Send panel with saved + custom recipients
        send_card = ctrl_page.locator("#send-report-card")
        if send_card.count() > 0:
            send_card.scroll_into_view_if_needed()
            # type a custom recipient into the custom recipient box
            ctrl_page.fill("#custom-email", "custom.auditor@domain.com")
            ctrl_page.fill("#custom-name", "Lead Auditor")
            ctrl_page.fill("#custom-role", "Auditor")
            send_card.screenshot(path="analytics/screenshots/final/04_controller_send_panel.png")
        else:
            ctrl_page.screenshot(path="analytics/screenshots/final/04_controller_send_panel.png")
        print("Captured 04_controller_send_panel.png")

        # 5. Feed stage mid-run (stepper clicked or feed advance)
        feed_card = ctrl_page.locator("#feed-simulation-card")
        if feed_card.count() > 0:
            feed_card.scroll_into_view_if_needed()
            feed_card.screenshot(path="analytics/screenshots/final/05_controller_feed_mid_run.png")
        print("Captured 05_controller_feed_mid_run.png")

        browser.close()

if __name__ == "__main__":
    capture_all()
