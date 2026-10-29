"""
stage10/audit/capture_day_screenshots.py

Feeds demo packs up to Day 1, captures screenshot of Day 1;
Feeds demo packs up to Day 7, captures screenshot of Day 7;
Then resets demo to 2025-12-31.
"""

from __future__ import annotations

import sys
from pathlib import Path
import time

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from playwright.sync_api import sync_playwright
from stage9.ops import reset_demo_v6, feed_next_queue_day
from stage9.current_day import get_current_day

def capture():
    print("Resetting to 2025-12-31...")
    reset_demo_v6(user="screenshot_capture")
    print("Current day:", get_current_day())

    # Feed Day 1
    print("Feeding Day 1 (2026-01-01)...")
    res1 = feed_next_queue_day(user="screenshot_capture")
    print("Feed result:", res1)
    print("Current day:", get_current_day())

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Desktop context
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        
        # Day 1 Desktop
        page.goto("http://localhost:8000/?date=2026-01-01", wait_until="networkidle")
        time.sleep(1)
        p1 = ROOT_DIR / "stage9" / "screenshots" / "today_day_1_desktop.png"
        p1_final = ROOT_DIR / "analytics" / "screenshots" / "final" / "viewer_today_day1.png"
        page.screenshot(path=str(p1), full_page=True)
        page.screenshot(path=str(p1_final), full_page=True)
        print("Captured Day 1 desktop:", p1)

        # Day 1 Mobile Viewport (iPhone width 390px)
        page.set_viewport_size({"width": 390, "height": 844})
        time.sleep(0.5)
        p1_m = ROOT_DIR / "stage9" / "screenshots" / "today_day_1_mobile.png"
        p1_m_final = ROOT_DIR / "analytics" / "screenshots" / "final" / "viewer_today_day1_mobile.png"
        page.screenshot(path=str(p1_m), full_page=True)
        page.screenshot(path=str(p1_m_final), full_page=True)
        print("Captured Day 1 mobile:", p1_m)

        # Feed up to Day 7
        for d in range(2, 8):
            print(f"Feeding Day {d}...")
            feed_next_queue_day(user="screenshot_capture")
        print("Current day after feeding up to Day 7:", get_current_day())

        # Day 7 Desktop
        page.set_viewport_size({"width": 1280, "height": 900})
        page.goto("http://localhost:8000/?date=2026-01-07", wait_until="networkidle")
        time.sleep(1)
        p7 = ROOT_DIR / "stage9" / "screenshots" / "today_day_7_desktop.png"
        p7_final = ROOT_DIR / "analytics" / "screenshots" / "final" / "viewer_today_day7.png"
        page.screenshot(path=str(p7), full_page=True)
        page.screenshot(path=str(p7_final), full_page=True)
        print("Captured Day 7 desktop:", p7)

        # Day 7 Mobile
        page.set_viewport_size({"width": 390, "height": 844})
        time.sleep(0.5)
        p7_m = ROOT_DIR / "stage9" / "screenshots" / "today_day_7_mobile.png"
        p7_m_final = ROOT_DIR / "analytics" / "screenshots" / "final" / "viewer_today_day7_mobile.png"
        page.screenshot(path=str(p7_m), full_page=True)
        page.screenshot(path=str(p7_m_final), full_page=True)
        print("Captured Day 7 mobile:", p7_m)

        browser.close()

    print("\nResetting demo back to 2025-12-31 baseline...")
    reset_demo_v6(user="screenshot_capture")
    print("Final current day:", get_current_day())
    print("Screenshots captured successfully.")

if __name__ == "__main__":
    capture()
