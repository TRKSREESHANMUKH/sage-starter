"""
stage9/test_summary_and_focus.py — Verification of Summary Box, Focus Boxes & Forecast Panel Rules.

Part C Specifications:
- C1: Summary box readability (<22 words/sentence, 4-6 sentences, plain words, brackets for technical terms, framing verbatim, numbers subset of facts, no INC_ tokens).
- C2: Forecast panel has no metric words (WAPE, MAPE, MAE, accuracy, model name, shortage badge).
- C3: Today's focus never empty for Days 0-10 and 20 random 2025 days; alert-driven first, routine checks on calm days.
- C4: Weekly focus (next 7 days) up to 5 items planned from known data only; traces to DB rows.
"""

from datetime import date, timedelta
import json
from pathlib import Path
import random
import re
import unittest

ROOT_DIR = Path(__file__).resolve().parent.parent

from app.database import SessionLocal
from stage9.current_day import get_current_day
from stage9.snapshot import compute_daily_snapshot
from stage9.priorities import compute_priorities
from stage9.status import RESEARCH_FRAMING
from web.one_page_data import (
    generate_plain_summary,
    validate_plain_summary,
    generate_today_focus_items,
    generate_weekly_focus_items,
    build_one_page_context
)


class TestSummaryAndFocus(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.db = SessionLocal()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_summary_readability_days_0_to_10(self):
        """C1: Summary text for Days 0 to 10 must pass all readability rules."""
        # Check Days 0 to 10
        demo_days = [date(2025, 12, 31)] + [date(2026, 1, d) for d in range(1, 11)]
        for d in demo_days:
            brief = build_one_page_context(selected_date_str=d.isoformat())
            summary = brief.get("plain_summary", {})
            sentences = summary.get("sentences", [])
            text = summary.get("text", "")

            # 4-6 sentences
            self.assertTrue(4 <= len(sentences) <= 6, f"Day {d} sentence count {len(sentences)} not in 4-6")

            # Max sentence length < 22 words
            for i, s in enumerate(sentences):
                word_count = len(s.split())
                self.assertLess(word_count, 22, f"Day {d} sentence {i+1} has {word_count} words (>=22): '{s}'")

            # Framing sentence verbatim
            self.assertIn(RESEARCH_FRAMING, text, f"Day {d} missing verbatim framing")

            # No INC_ tokens
            self.assertNotIn("INC_", text, f"Day {d} contains INC_ answer-key token")
            self.assertNotIn("business_events", text, f"Day {d} contains business_events token")

            # Validator check
            valid, msg = validate_plain_summary(text)
            self.assertTrue(valid, f"Day {d} failed validate_plain_summary: {msg}")

    def test_focus_never_empty_days_0_to_10_and_20_random_2025_days(self):
        """C3: Today's focus and weekly focus must never be empty for Days 0-10 and 20 random 2025 days."""
        demo_days = [date(2025, 12, 31)] + [date(2026, 1, d) for d in range(1, 11)]

        # Pick 20 deterministic random days from 2025
        rng = random.Random(42)
        start_2025 = date(2025, 1, 15)
        random_days = [start_2025 + timedelta(days=rng.randint(0, 340)) for _ in range(20)]

        all_test_days = demo_days + random_days

        for d in all_test_days:
            brief = build_one_page_context(selected_date_str=d.isoformat())
            today_focus = brief.get("today_focus", [])
            weekly_focus = brief.get("weekly_focus", [])

            self.assertGreater(len(today_focus), 0, f"Day {d} today_focus is empty")
            self.assertLessEqual(len(today_focus), 5, f"Day {d} today_focus has more than 5 items")

            self.assertGreater(len(weekly_focus), 0, f"Day {d} weekly_focus is empty")
            self.assertLessEqual(len(weekly_focus), 5, f"Day {d} weekly_focus has more than 5 items")

            # Check that each today focus item has required keys
            for item in today_focus:
                self.assertIn("action", item)
                self.assertIn("owner_role", item)
                self.assertIn("target_time", item)
                self.assertIn("reason", item)
                self.assertIn("root_fix", item)

    def test_forecast_panel_has_no_metric_words(self):
        """C2: Forecast panel in UI must not contain metric words."""
        brief = build_one_page_context(selected_date_str="2025-12-31")
        fc = brief.get("forecast_strip", {})

        # Ensure no metrics in forecast strip
        forbidden = ["WAPE", "MAPE", "MAE", "accuracy", "Oracle", "Gradient Boosting", "Count Regression"]
        fc_str = json.dumps(fc)
        for term in forbidden:
            self.assertNotIn(term.lower(), fc_str.lower(), f"Forecast strip contains forbidden metric term '{term}'")


if __name__ == "__main__":
    unittest.main()
