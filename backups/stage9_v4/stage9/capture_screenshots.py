"""
stage9/capture_screenshots.py — Capture verified screenshots of the Insights tab.

Captures:
1. Eventful date (2025-02-03) with one supplier row expanded.
2. Calm date (2025-01-15) with one supplier row expanded.
Saved to artifacts directory: /Users/asl/.gemini/antigravity/brain/54922590-fb4c-4090-afba-eccf52787f8d/
"""

import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

ARTIFACT_DIR = Path("/Users/asl/.gemini/antigravity/brain/54922590-fb4c-4090-afba-eccf52787f8d")
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

def capture_insights_screenshots():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        # Responsive desktop viewport
        page = browser.new_page(viewport={"width": 1280, "height": 1800})

        # 1. Eventful Date: 2025-02-03
        url_eventful = "http://127.0.0.1:8000/insights?date=2025-02-03&period=ytd"
        print(f"Navigating to {url_eventful}...")
        page.goto(url_eventful, wait_until="networkidle")
        time.sleep(1.0) # wait for Chart.js animation

        # Expand the first supplier's deliveries row
        first_details = page.locator("#supplier-report-card details").first
        if first_details.count() > 0:
            first_details.click()
            time.sleep(0.5)

        eventful_path = ARTIFACT_DIR / "insights_eventful_2025-02-03.png"
        page.screenshot(path=str(eventful_path), full_page=True)
        print(f"Saved eventful screenshot: {eventful_path}")

        # 2. Calm Date: 2025-01-15
        url_calm = "http://127.0.0.1:8000/insights?date=2025-01-15&period=ytd"
        print(f"Navigating to {url_calm}...")
        page.goto(url_calm, wait_until="networkidle")
        time.sleep(1.0) # wait for Chart.js animation

        # Expand the first supplier's deliveries row
        first_details = page.locator("#supplier-report-card details").first
        if first_details.count() > 0:
            first_details.click()
            time.sleep(0.5)

        calm_path = ARTIFACT_DIR / "insights_calm_2025-01-15.png"
        page.screenshot(path=str(calm_path), full_page=True)
        print(f"Saved calm screenshot: {calm_path}")

        browser.close()

if __name__ == "__main__":
    capture_insights_screenshots()
