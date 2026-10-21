"""
stage9/capture_screenshots.py — Captures all required UI screenshots for Final 2 report.
"""

from __future__ import annotations

import os
from pathlib import Path
from playwright.sync_api import sync_playwright

from stage9.ops import jump_to_case

ARTIFACT_DIR = Path("/Users/asl/.gemini/antigravity/brain/54922590-fb4c-4090-afba-eccf52787f8d")
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)


def capture_all():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # 1. Case 7 (Crisis peak with Click to analyze open)
        print("Capturing Case 7 (Crisis peak)...")
        jump_to_case(7, user="screenshot_tool")
        page = browser.new_page(viewport={"width": 1280, "height": 1100})
        page.goto("http://127.0.0.1:8000/?token=sage_dev_token_2025", wait_until="networkidle")
        # Open click to analyze
        details = page.locator("details.analyze-expander").first
        if details.count() > 0:
            details.evaluate("el => el.open = true")
        page.wait_for_timeout(1000)
        c7_path = ARTIFACT_DIR / "case_07_crisis_peak.png"
        page.screenshot(path=str(c7_path), full_page=True)
        print(f"  Saved {c7_path}")

        # 2. Case 5 (Buffer held with Click to analyze open)
        print("Capturing Case 5 (Buffer held)...")
        jump_to_case(5, user="screenshot_tool")
        page.goto("http://127.0.0.1:8000/?token=sage_dev_token_2025", wait_until="networkidle")
        details = page.locator("details.analyze-expander").first
        if details.count() > 0:
            details.evaluate("el => el.open = true")
        page.wait_for_timeout(1000)
        c5_path = ARTIFACT_DIR / "case_05_buffer_held.png"
        page.screenshot(path=str(c5_path), full_page=True)
        print(f"  Saved {c5_path}")

        # 3. Case 9 (Quiet day with green banner)
        print("Capturing Case 9 (Quiet control day)...")
        jump_to_case(9, user="screenshot_tool")
        page.goto("http://127.0.0.1:8000/?token=sage_dev_token_2025", wait_until="networkidle")
        page.wait_for_timeout(1000)
        c9_path = ARTIFACT_DIR / "case_09_quiet_day.png"
        page.screenshot(path=str(c9_path), full_page=True)
        print(f"  Saved {c9_path}")

        # 4. Method Tab (Coverage Block)
        print("Capturing Method Tab Coverage Block...")
        page.goto("http://127.0.0.1:8000/method?token=sage_dev_token_2025", wait_until="networkidle")
        page.wait_for_timeout(1000)
        method_path = ARTIFACT_DIR / "method_coverage_block.png"
        page.screenshot(path=str(method_path), full_page=True)
        print(f"  Saved {method_path}")

        # 5. Controller Demo Cases Section
        print("Capturing Controller Demo Cases Section...")
        page.goto("http://127.0.0.1:8001/ctrl/login", wait_until="networkidle")
        # Login to controller
        ctrl_token = os.getenv("SAGE_CONTROLLER_TOKEN", "sage_operator_token_2025")
        page.fill("input[name='token']", ctrl_token)
        page.click("button[type='submit']")
        page.wait_for_url("**/ctrl/**")
        page.wait_for_timeout(1000)
        ctrl_path = ARTIFACT_DIR / "controller_demo_cases.png"
        page.screenshot(path=str(ctrl_path), full_page=True)
        print(f"  Saved {ctrl_path}")

        browser.close()
    print("All screenshots captured successfully!")


if __name__ == "__main__":
    capture_all()
