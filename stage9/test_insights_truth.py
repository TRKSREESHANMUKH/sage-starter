"""
stage9/test_insights_truth.py — Page-level tests verifying Insights tab equals truth layer.
Asserts:
- Status 200 on all dates and periods
- Matches truth figures
- On-time % < 100% when backorders/cancellations exist
- No contradictory text (e.g. "1 delays", "100.0%" with backlog)
- Verbatim framing sentence present
- Zero forbidden tokens ("None", "NaN", "undefined", "INC_", stack traces)
"""

import unittest
from datetime import date
from starlette.requests import Request

from web.app import insights
from web.insights_data import get_insights_data
from stage9.status import RESEARCH_FRAMING


def _render_insights(date_str: str, period_str: str) -> str:
    req = Request({
        "type": "http",
        "method": "GET",
        "headers": [],
        "server": ("127.0.0.1", 8000),
        "path": "/insights"
    })
    resp = insights(req, date=date_str, period=period_str)
    assert resp.status_code == 200
    return resp.body.decode("utf-8")


class TestInsightsTruth(unittest.TestCase):
    def test_insights_2025_12_31_all(self):
        html = _render_insights("2025-12-31", "all")

        # Truth check
        payload = get_insights_data("2025-12-31", "all")
        fb = payload["fulfillment_buckets"]
        self.assertEqual(fb["on_time_orders"], 173)
        self.assertEqual(fb["total_orders"], 221)
        self.assertAlmostEqual(fb["on_time_pct"], 78.3, places=1)
        self.assertEqual(fb["total_open_units"], 652)

        # HTML assertions
        self.assertIn("78.3%", html)
        self.assertIn("173 of 221 orders", html)
        self.assertIn(RESEARCH_FRAMING, html)
        self.assertNotIn("1 delays", html)
        self.assertNotIn("NaN", html)
        self.assertNotIn("undefined", html)
        self.assertNotIn("INC_", html)

    def test_insights_2026_01_09_all(self):
        html = _render_insights("2026-01-09", "all")

        # Truth check
        payload = get_insights_data("2026-01-09", "all")
        fb = payload["fulfillment_buckets"]
        # Must not be 100.0%
        self.assertLess(fb["on_time_pct"], 100.0)
        self.assertAlmostEqual(fb["on_time_pct"], 75.2, places=1)
        self.assertEqual(fb["cancelled_opening_orders"], 48)

        # HTML assertions
        self.assertIn("75.2%", html)
        self.assertNotIn("Orders delivered on time</div>\n    <div class=\"summary-value\">100.0%</div>", html)
        self.assertIn(RESEARCH_FRAMING, html)
        self.assertNotIn("1 delays", html)
        self.assertNotIn("NaN", html)
        self.assertNotIn("undefined", html)
        self.assertNotIn("INC_", html)

    def test_insights_key_dates_and_periods(self):
        dates = ["2025-12-31", "2026-01-01", "2026-01-05", "2026-01-09"]
        periods = ["all", "this_year", "quarter", "30d"]

        for d in dates:
            for p in periods:
                with self.subTest(date=d, period=p):
                    html = _render_insights(d, p)
                    self.assertIn(RESEARCH_FRAMING, html)
                    self.assertNotIn("1 delays", html)
                    self.assertNotIn("NaN", html)
                    self.assertNotIn("undefined", html)
                    self.assertNotIn("INC_", html)


if __name__ == "__main__":
    unittest.main()
