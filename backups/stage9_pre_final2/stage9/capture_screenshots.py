import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT_DIR = Path(__file__).resolve().parent.parent
SCREENSHOTS_DIR = ROOT_DIR / "stage9" / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

def capture():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()

        # 1. Today page with header buttons (date=2025-02-03)
        print("Capturing Today page...")
        page.goto("http://127.0.0.1:8000/?date=2025-02-03", wait_until="networkidle")
        page.screenshot(path=str(SCREENSHOTS_DIR / "today_page_2025-02-03.png"), full_page=False)

        # 1b. Header detail
        header_el = page.locator(".demo-header")
        if header_el.count() > 0:
            header_el.screenshot(path=str(SCREENSHOTS_DIR / "header_controls.png"))

        # 2. Insights Eventful Day (2025-02-03)
        print("Capturing Insights eventful day...")
        page.goto("http://127.0.0.1:8000/insights?date=2025-02-03&period=ytd", wait_until="networkidle")
        page.screenshot(path=str(SCREENSHOTS_DIR / "insights_eventful_2025-02-03.png"), full_page=True)

        # 3. Insights Calm Day (2025-01-15)
        print("Capturing Insights calm day...")
        page.goto("http://127.0.0.1:8000/insights?date=2025-01-15&period=ytd", wait_until="networkidle")
        page.screenshot(path=str(SCREENSHOTS_DIR / "insights_calm_2025-01-15.png"), full_page=True)

        browser.close()
        print("All screenshots captured in", SCREENSHOTS_DIR)

if __name__ == "__main__":
    capture()
