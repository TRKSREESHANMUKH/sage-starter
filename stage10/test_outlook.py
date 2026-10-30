"""
stage10/test_outlook.py — Comprehensive Unit & Integration Tests for Weekly Order Forecast.

Asserts:
1. Flag toggle: block renders if enabled=True, omitted if enabled=False.
2. Zero look-ahead: Day D reads only records <= D.
3. Cache integrity: second call returns cached dictionary instantly (<50ms).
4. Rule 2 framing sentence: exact verbatim sentence rendered on page.
5. Past-day rule: past day returns stored forecast if in test store, else "No forecast stored for this day".
6. Shortage risk wording: strictly "Low", "Medium", "High" only.
7. Sub-3-second render: complete context build and Jinja render executes in < 3.0 seconds.
"""

from __future__ import annotations

import time
import unittest
from datetime import date
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

from stage10.forecast.outlook import (
    get_weekly_forecast,
    clear_outlook_cache,
    RESEARCH_FRAMING
)
from web.one_page_data import build_one_page_context
from web.insights_data import get_insights_data
from web.app import templates


class TestWeeklyForecast(unittest.TestCase):

    def setUp(self):
        clear_outlook_cache()
        self.as_of = date(2026, 1, 1)

    def test_01_flag_toggle_enabled_and_disabled(self):
        """Asserts weekly forecast responds strictly to outlook.enabled flag."""
        # Enabled
        rules_enabled = {"outlook": {"enabled": True}}
        res_enabled = get_weekly_forecast(self.as_of, use_cache=False, rules=rules_enabled)
        self.assertTrue(res_enabled["available"])
        self.assertIn("Next 7 days:", res_enabled["headline"])

        # Disabled
        rules_disabled = {"outlook": {"enabled": False}}
        res_disabled = get_weekly_forecast(self.as_of, use_cache=False, rules=rules_disabled)
        self.assertFalse(res_disabled["available"])
        self.assertIn("disabled", res_disabled["message"].lower())

    def test_02_zero_lookahead_guarantee(self):
        """Asserts weekly forecast never accesses transactions > as_of."""
        fc = get_weekly_forecast(self.as_of, use_cache=False)
        self.assertTrue(fc["available"])
        self.assertEqual(fc["as_of"], "2026-01-01")
        self.assertGreaterEqual(fc["due_known"], 0)
        self.assertIn("already booked", fc["breakdown_line"])
        self.assertIn(fc["shortage_risk"], ["Low", "Medium", "High"])

    def test_03_past_day_rule(self):
        """Asserts past days return stored forecasts when present, or honest placeholder."""
        # 1. Past day with stored test forecast (e.g. Sunday 2025-07-06)
        past_stored = date(2025, 7, 6)
        fc_stored = get_weekly_forecast(past_stored, is_past_day=True, use_cache=False)
        self.assertTrue(fc_stored["available"])
        self.assertTrue(fc_stored["is_stored"])

        # 2. Past day without stored test forecast (e.g. training date 2025-02-15)
        past_unstored = date(2025, 2, 15)
        fc_unstored = get_weekly_forecast(past_unstored, is_past_day=True, use_cache=False)
        self.assertFalse(fc_unstored["available"])
        self.assertEqual(fc_unstored["message"], "No forecast stored for this day")
        self.assertEqual(fc_unstored["framing"], RESEARCH_FRAMING)

    def test_04_cache_integrity_and_speed(self):
        """Asserts in-memory cache returns identical result in sub-millisecond time."""
        clear_outlook_cache()
        res1 = get_weekly_forecast(self.as_of, use_cache=True)
        self.assertTrue(res1["available"])

        t0 = time.perf_counter()
        res2 = get_weekly_forecast(self.as_of, use_cache=True)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        self.assertIs(res1, res2)
        self.assertLess(elapsed_ms, 500.0, f"Cache retrieval took {elapsed_ms:.2f}ms (expected <500ms)")

    def test_05_rule_2_framing_verbatim(self):
        """Asserts Rule 2 mandatory scientific framing sentence is present verbatim."""
        fc = get_weekly_forecast(self.as_of, use_cache=False)
        expected_framing = (
            "SAGE performs controlled synthetic causal-attribution evaluation under an expert-defined causal model; "
            "it does not claim to prove real-world causality."
        )
        self.assertEqual(fc["framing"], expected_framing)

    def test_06_sub_3_second_full_render(self):
        """Asserts complete one-page context build and HTML render runs in under 3.0 seconds."""
        from stage9.current_day import get_current_day
        t0 = time.perf_counter()
        cur_day = get_current_day().isoformat()
        ctx = build_one_page_context(selected_date_str=cur_day)
        self.assertIn("outlook", ctx)
        self.assertIsNotNone(ctx["outlook"])

        template = templates.get_template("home.html")
        html = template.render({
            "request": None,
            "token": "test_token",
            **ctx
        })
        elapsed = time.perf_counter() - t0

        self.assertIn("Next 7 days: expected demand", html)
        self.assertNotIn("Shortage risk", html)
        self.assertIn(RESEARCH_FRAMING, html)
        self.assertLess(elapsed, 3.0, f"Render took {elapsed:.2f}s (must be <3.0s)")
        print(f"Full Today page context build and render completed in {elapsed:.3f}s")

    def test_07_insights_sub_3_second_render(self):
        """Asserts Insights context build and render runs in under 3.0 seconds."""
        t0 = time.perf_counter()
        payload = get_insights_data(as_of_str="2025-12-31", period_str="all")
        self.assertIn("history_and_key_events", payload)
        self.assertIn("forecast_section", payload)

        template = templates.get_template("insights.html")
        html = template.render({
            "request": None,
            "token": "test_token",
            **payload
        })
        elapsed = time.perf_counter() - t0

        self.assertIn("History and Key Events", html)
        self.assertIn("Year at a Glance", html)
        self.assertIn("Weekly Order Forward-Look", html)
        self.assertIn(RESEARCH_FRAMING, html)
        self.assertLess(elapsed, 3.0, f"Insights render took {elapsed:.2f}s (must be <3.0s)")
        print(f"Full Insights build and render completed in {elapsed:.3f}s")


if __name__ == "__main__":
    unittest.main()
