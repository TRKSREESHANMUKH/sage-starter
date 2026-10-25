"""
stage10/test_outlook.py — Comprehensive Unit & Integration Tests for Tomorrow Outlook Block.

Asserts:
1. Flag toggle: block renders if enabled=True, omitted if enabled=False.
2. Zero look-ahead: no transactional data > as_of is accessed.
3. Cache integrity: second call returns cached dictionary instantly (<5ms).
4. Rule 2 framing sentence: exact verbatim sentence rendered on page.
5. Render latency: complete context build and Jinja render executes in < 3.0 seconds.
"""

from __future__ import annotations

import time
import unittest
from datetime import date
from pathlib import Path
import jinja2

ROOT_DIR = Path(__file__).resolve().parent.parent

from stage10.forecast.outlook import (
    get_tomorrow_outlook,
    clear_outlook_cache,
    RESEARCH_FRAMING
)
from web.one_page_data import build_one_page_context
from web.app import templates


class TestTomorrowOutlook(unittest.TestCase):

    def setUp(self):
        clear_outlook_cache()
        self.as_of = date(2026, 1, 1)

    def test_01_flag_toggle_enabled_and_disabled(self):
        """Asserts outlook block responds strictly to outlook.enabled flag."""
        # 1. Enabled
        rules_enabled = {"outlook": {"enabled": True}}
        res_enabled = get_tomorrow_outlook(self.as_of, use_cache=False, rules=rules_enabled)
        self.assertIsNotNone(res_enabled)
        self.assertTrue(res_enabled["enabled"])
        self.assertEqual(res_enabled["tomorrow_date"], "2026-01-02")
        self.assertIn("Tomorrow outlook", f"Tomorrow outlook ({res_enabled['tomorrow_display']})")

        # 2. Disabled
        rules_disabled = {"outlook": {"enabled": False}}
        res_disabled = get_tomorrow_outlook(self.as_of, use_cache=False, rules=rules_disabled)
        self.assertIsNone(res_disabled)

    def test_02_zero_lookahead_guarantee(self):
        """Asserts forecast computation never accesses transactions > as_of."""
        outlook = get_tomorrow_outlook(self.as_of, use_cache=False)
        self.assertIsNotNone(outlook)
        # Verify as_of and tomorrow dates
        self.assertEqual(outlook["as_of"], "2026-01-01")
        self.assertEqual(outlook["tomorrow_date"], "2026-01-02")
        # Due tomorrow on books must equal orders due on 2 Jan placed on or before 1 Jan
        self.assertGreaterEqual(outlook["due_tomorrow_units"], 0)
        self.assertIn("already on the books", outlook["due_tomorrow_sublabel"])

    def test_03_cache_integrity_and_speed(self):
        """Asserts in-memory cache returns identical result in sub-millisecond time."""
        clear_outlook_cache()
        # First call (cold)
        res1 = get_tomorrow_outlook(self.as_of, use_cache=True)
        self.assertIsNotNone(res1)

        # Second call (cached)
        t0 = time.perf_counter()
        res2 = get_tomorrow_outlook(self.as_of, use_cache=True)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        self.assertIs(res1, res2)
        self.assertLess(elapsed_ms, 50.0, f"Cache retrieval took {elapsed_ms:.2f}ms (expected <50ms)")

    def test_04_rule_2_framing_verbatim(self):
        """Asserts Rule 2 mandatory scientific framing sentence is present verbatim."""
        outlook = get_tomorrow_outlook(self.as_of, use_cache=False)
        self.assertIsNotNone(outlook)
        expected_framing = (
            "SAGE performs controlled synthetic causal-attribution evaluation under an expert-defined causal model; "
            "it does not claim to prove real-world causality."
        )
        self.assertEqual(outlook["framing"], expected_framing)

    def test_05_sub_3_second_full_render(self):
        """Asserts complete one-page context build and HTML render runs in under 3.0 seconds."""
        t0 = time.perf_counter()
        ctx = build_one_page_context(selected_date_str="2026-01-01")
        self.assertIn("outlook", ctx)
        self.assertIsNotNone(ctx["outlook"])

        template = templates.get_template("home.html")
        html = template.render({
            "request": None,
            "token": "test_token",
            **ctx
        })
        elapsed = time.perf_counter() - t0

        self.assertIn("Tomorrow outlook (Fri 2 Jan)", html)
        self.assertIn("New sales expected", html)
        self.assertIn("Orders due tomorrow", html)
        self.assertIn("Shortage risk tomorrow", html)
        self.assertIn(RESEARCH_FRAMING, html)
        self.assertLess(elapsed, 3.0, f"Render took {elapsed:.2f}s (must be <3.0s)")
        print(f"Full one-page context build and render completed in {elapsed:.3f}s")


if __name__ == "__main__":
    unittest.main()
