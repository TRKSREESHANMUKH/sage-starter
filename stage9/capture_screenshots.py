"""
stage9/capture_screenshots.py — SAGE Stage 9 Final Screenshot Generator.

Regenerates clean, verified screenshots:
1. viewer_today_day1.png (desktop) & viewer_today_day1_mobile.png (mobile)
2. viewer_today_day7.png (desktop) & viewer_today_day7_mobile.png (mobile)
3. viewer_today_day10.png (desktop)
4. viewer_insights_forecast.png (showing Protocol v4 table and plain-English disclosures)
5. viewer_insights_history.png (showing calendar heat grid and key events list)
6. viewer_method.png (showing disclosures)
7. controller_dashboard.png
8. sample_daily_brief_pdf.png
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
        desktop_ctx = browser.new_context(viewport={"width": 1280, "height": 1100})
        mobile_ctx = browser.new_context(viewport={"width": 375, "height": 812}, is_mobile=True)

        for ctx in [desktop_ctx, mobile_ctx]:
            if web_token:
                ctx.add_cookies([{
                    "name": "sage_token",
                    "value": web_token,
                    "domain": "127.0.0.1",
                    "path": "/"
                }])

        dpage = desktop_ctx.new_page()
        mpage = mobile_ctx.new_page()

        # Log into viewer
        dpage.goto("http://127.0.0.1:8000/login")
        dpage.fill("#username_or_email", "admin")
        dpage.fill("#password", "SageAdmin2026!")
        dpage.click("button[type='submit']")
        dpage.wait_for_load_state("domcontentloaded")

        mpage.goto("http://127.0.0.1:8000/login")
        mpage.fill("#username_or_email", "admin")
        mpage.fill("#password", "SageAdmin2026!")
        mpage.click("button[type='submit']")
        mpage.wait_for_load_state("domcontentloaded")

        # 1. Day 1 (Desktop + Mobile)
        print("Capturing Viewer Day 1 (desktop & mobile)...")
        dpage.goto("http://127.0.0.1:8000/?date=2026-01-01", wait_until="domcontentloaded")
        dpage.wait_for_timeout(1000)
        p1_d = FINAL_DIR / "viewer_today_day1.png"
        dpage.screenshot(path=str(p1_d), full_page=True)
        print(f"  Saved {p1_d}")

        mpage.goto("http://127.0.0.1:8000/?date=2026-01-01", wait_until="domcontentloaded")
        mpage.wait_for_timeout(1000)
        p1_m = FINAL_DIR / "viewer_today_day1_mobile.png"
        mpage.screenshot(path=str(p1_m), full_page=True)
        print(f"  Saved {p1_m}")

        # 2. Day 3 (Supplier delay)
        dpage.goto("http://127.0.0.1:8000/?date=2026-01-03", wait_until="domcontentloaded")
        dpage.wait_for_timeout(1000)
        p3_d = FINAL_DIR / "viewer_today_day3.png"
        dpage.screenshot(path=str(p3_d), full_page=True)

        # 3. Day 7 (Desktop + Mobile)
        print("Capturing Viewer Day 7 (desktop & mobile)...")
        dpage.goto("http://127.0.0.1:8000/?date=2026-01-07", wait_until="domcontentloaded")
        dpage.wait_for_timeout(1000)
        details = dpage.locator("details.analyze-expander").first
        if details.count() > 0:
            details.evaluate("el => el.open = true")
        dpage.wait_for_timeout(1000)
        p7_d = FINAL_DIR / "viewer_today_day7.png"
        dpage.screenshot(path=str(p7_d), full_page=True)
        print(f"  Saved {p7_d}")

        mpage.goto("http://127.0.0.1:8000/?date=2026-01-07", wait_until="domcontentloaded")
        mpage.wait_for_timeout(1000)
        p7_m = FINAL_DIR / "viewer_today_day7_mobile.png"
        mpage.screenshot(path=str(p7_m), full_page=True)
        print(f"  Saved {p7_m}")

        # 4. Day 9
        dpage.goto("http://127.0.0.1:8000/?date=2026-01-09", wait_until="domcontentloaded")
        dpage.wait_for_timeout(1000)
        p9_d = FINAL_DIR / "viewer_today_day9.png"
        dpage.screenshot(path=str(p9_d), full_page=True)

        # 5. Day 10 (Desktop + Mobile)
        print("Capturing Viewer Day 10 (desktop & mobile)...")
        dpage.goto("http://127.0.0.1:8000/?date=2026-01-10", wait_until="domcontentloaded")
        dpage.wait_for_timeout(1000)
        p10_d = FINAL_DIR / "viewer_today_day10.png"
        dpage.screenshot(path=str(p10_d), full_page=True)
        print(f"  Saved {p10_d}")

        mpage.goto("http://127.0.0.1:8000/?date=2026-01-10", wait_until="domcontentloaded")
        mpage.wait_for_timeout(1000)
        p10_m = FINAL_DIR / "viewer_today_day10_mobile.png"
        mpage.screenshot(path=str(p10_m), full_page=True)
        print(f"  Saved {p10_m}")

        # 6. Insights Forecast Section
        print("Capturing Insights Forecast Section...")
        dpage.goto("http://127.0.0.1:8000/insights?date=2026-01-10#forecast", wait_until="domcontentloaded")
        dpage.wait_for_timeout(1000)
        p_fc = FINAL_DIR / "viewer_insights_forecast.png"
        dpage.screenshot(path=str(p_fc), full_page=True)
        print(f"  Saved {p_fc}")

        # 7. Insights History Section
        print("Capturing Insights History Section...")
        dpage.goto("http://127.0.0.1:8000/insights?date=2026-01-10#history", wait_until="domcontentloaded")
        dpage.wait_for_timeout(1000)
        p_hist = FINAL_DIR / "viewer_insights_history.png"
        dpage.screenshot(path=str(p_hist), full_page=True)
        print(f"  Saved {p_hist}")

        # 8. Method Page
        print("Capturing Method Page...")
        dpage.goto("http://127.0.0.1:8000/method", wait_until="domcontentloaded")
        dpage.wait_for_timeout(1000)
        p_meth = FINAL_DIR / "viewer_method.png"
        dpage.screenshot(path=str(p_meth), full_page=True)
        print(f"  Saved {p_meth}")

        # 9. Controller Dashboard
        print("Capturing Controller Dashboard...")
        ctrl_page = desktop_ctx.new_page()
        ctrl_page.goto("http://127.0.0.1:8001/ctrl/login", wait_until="domcontentloaded")
        ctrl_page.fill("#username_or_email", "admin")
        ctrl_page.fill("#password", "SageAdmin2026!")
        ctrl_page.click("button[type='submit']")
        ctrl_page.wait_for_url("**/ctrl/**")
        ctrl_page.wait_for_timeout(1000)
        p_ctrl = FINAL_DIR / "controller_dashboard.png"
        ctrl_page.screenshot(path=str(p_ctrl), full_page=True)
        print(f"  Saved {p_ctrl}")

        # 10. Sample 1-Page PDF preview
        report_html = ROOT_DIR / "reports" / "2026-01-07" / "report.html"
        if report_html.exists():
            print("Capturing Sample 1-Page PDF preview...")
            pdf_page = desktop_ctx.new_page()
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
