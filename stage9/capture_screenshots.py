"""
stage9/capture_screenshots.py — SAGE Stage 9 Final Screenshot Generator.

Regenerates clean, verified screenshots from the authentic 2026 demo feed:
1. Viewer Today Day 1 (Normal baseline)
2. Viewer Today Day 3 (Supplier delay, buffer holding)
3. Viewer Today Day 7 (Crisis peak with 'Click to analyze' expander open)
4. Viewer Today Day 9 (Seasonal peak / control day)
5. Viewer Today Day 10 (Dual minor issues)
6. Insights Tab on 2025-12-31 (78.3% on-time truth)
7. Insights Tab on 2026-01-09 (75.2% on-time truth)
8. Controller Dashboard on port 8001
9. Sample 1-Page Daily Brief PDF Render
"""

import os
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT_DIR = Path(__file__).resolve().parent.parent
FINAL_DIR = ROOT_DIR / "analytics" / "screenshots" / "final"
FINAL_DIR.mkdir(parents=True, exist_ok=True)


def capture_all():
    web_token = os.getenv("SAGE_WEB_TOKEN", "")
    ctrl_token = os.getenv("SAGE_CONTROLLER_TOKEN", "")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 1100})

        # Set auth cookie for viewer
        if web_token:
            context.add_cookies([{
                "name": "sage_token",
                "value": web_token,
                "domain": "127.0.0.1",
                "path": "/"
            }])

        page = context.new_page()

        # 1. Day 1 (Normal baseline)
        print("Capturing Viewer Day 1...")
        page.goto("http://127.0.0.1:8000/?date=2026-01-01", wait_until="domcontentloaded")
        page.wait_for_timeout(1000)
        p1 = FINAL_DIR / "viewer_today_day1.png"
        page.screenshot(path=str(p1), full_page=True)
        print(f"  Saved {p1}")

        # 2. Day 3 (Supplier delay)
        print("Capturing Viewer Day 3...")
        page.goto("http://127.0.0.1:8000/?date=2026-01-03", wait_until="domcontentloaded")
        page.wait_for_timeout(1000)
        p3 = FINAL_DIR / "viewer_today_day3.png"
        page.screenshot(path=str(p3), full_page=True)
        print(f"  Saved {p3}")

        # 3. Day 7 (Crisis peak with Click to analyze open)
        print("Capturing Viewer Day 7 (Click to analyze open)...")
        page.goto("http://127.0.0.1:8000/?date=2026-01-07", wait_until="domcontentloaded")
        page.wait_for_timeout(1000)
        details = page.locator("details.analyze-expander").first
        if details.count() > 0:
            details.evaluate("el => el.open = true")
        page.wait_for_timeout(1000)
        p7 = FINAL_DIR / "viewer_today_day7.png"
        page.screenshot(path=str(p7), full_page=True)
        print(f"  Saved {p7}")

        # 4. Day 9 (Control day)
        print("Capturing Viewer Day 9...")
        page.goto("http://127.0.0.1:8000/?date=2026-01-09", wait_until="domcontentloaded")
        page.wait_for_timeout(1000)
        p9 = FINAL_DIR / "viewer_today_day9.png"
        page.screenshot(path=str(p9), full_page=True)
        print(f"  Saved {p9}")

        # 5. Day 10 (Dual minor issues)
        print("Capturing Viewer Day 10...")
        page.goto("http://127.0.0.1:8000/?date=2026-01-10", wait_until="domcontentloaded")
        page.wait_for_timeout(1000)
        p10 = FINAL_DIR / "viewer_today_day10.png"
        page.screenshot(path=str(p10), full_page=True)
        print(f"  Saved {p10}")

        # 6. Insights 2025-12-31
        print("Capturing Insights 2025-12-31...")
        page.goto("http://127.0.0.1:8000/insights?date=2025-12-31&period=all", wait_until="domcontentloaded")
        page.wait_for_timeout(1000)
        pi_25 = FINAL_DIR / "viewer_insights_2025-12-31.png"
        page.screenshot(path=str(pi_25), full_page=True)
        print(f"  Saved {pi_25}")

        # 7. Insights 2026-01-09
        print("Capturing Insights 2026-01-09...")
        page.goto("http://127.0.0.1:8000/insights?date=2026-01-09&period=all", wait_until="domcontentloaded")
        page.wait_for_timeout(1000)
        pi_26 = FINAL_DIR / "viewer_insights_2026-01-09.png"
        page.screenshot(path=str(pi_26), full_page=True)
        print(f"  Saved {pi_26}")

        # 8. Controller Dashboard
        print("Capturing Controller Dashboard...")
        ctrl_page = context.new_page()
        ctrl_page.goto("http://127.0.0.1:8001/ctrl/login", wait_until="domcontentloaded")
        ctrl_page.fill("input[name='token']", ctrl_token)
        ctrl_page.click("button[type='submit']")
        ctrl_page.wait_for_url("**/ctrl/**")
        ctrl_page.wait_for_timeout(1000)
        p_ctrl = FINAL_DIR / "controller_dashboard.png"
        ctrl_page.screenshot(path=str(p_ctrl), full_page=True)
        print(f"  Saved {p_ctrl}")

        # 9. Sample 1-Page PDF preview
        report_html = ROOT_DIR / "reports" / "2026-01-07" / "report.html"
        if report_html.exists():
            print("Capturing Sample 1-Page PDF preview...")
            pdf_page = context.new_page()
            pdf_page.set_viewport_size({"width": 800, "height": 1130})
            pdf_page.goto(f"file://{report_html.resolve()}", wait_until="load")
            pdf_page.wait_for_timeout(500)
            p_pdf = FINAL_DIR / "sample_daily_brief_pdf.png"
            pdf_page.screenshot(path=str(p_pdf))
            print(f"  Saved {p_pdf}")

        browser.close()
        print("\nAll screenshots generated successfully into analytics/screenshots/final/")


if __name__ == "__main__":
    capture_all()
