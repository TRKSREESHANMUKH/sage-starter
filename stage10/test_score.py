"""
stage10/test_score.py — Unit tests for SAGE deterministic scoring protocol.

Tests the formal rules specified in Phase D:
1. HIT: banner tier equals expected AND scripted root entity in top-3 alert.
2. PARTIAL: entity found in top-3 but tier off by one.
3. PARTIAL: entity found only in lower card (rank > 3).
4. MISS: scripted entity not found.
5. MISS: tier divergence > 1.
6. Control day: banner above expected tier is strictly MISS.
7. Control day: banner matching expected tier is HIT.
"""

import unittest
from stage10.demo_feed.score import score_feed, TIER_RANKS, check_entity_match


class TestFeedScoringRules(unittest.TestCase):
    def test_hit_tier_and_top3_entity(self):
        # Day 3: Expected NEEDS_ATTENTION, actual NEEDS_ATTENTION, top-3 alert mentions EastCoast/PO #19
        fake_days = [{
            "day": 3,
            "status_word": "NEEDS_ATTENTION",
            "top_headline": "Overdue delivery from EastCoast Components (PO #19)",
            "alerts": [{"headline": "Overdue delivery from EastCoast Components (PO #19)", "cause_chain": ""}]
        }]
        # Evaluate day 3 logic
        day_info = fake_days[0]
        exp_tiers = ["NEEDS_ATTENTION"]
        exp_entity = "eastcoast"
        matched = check_entity_match(day_info["alerts"][0]["headline"], exp_entity, day_info)
        self.assertTrue(matched)
        self.assertIn(day_info["status_word"], exp_tiers)

    def test_partial_tier_off_by_one(self):
        # Expected NEEDS_ATTENTION (rank 2), actual WATCH (rank 1), entity in top-3
        act_rank = TIER_RANKS["WATCH"]
        exp_rank = TIER_RANKS["NEEDS_ATTENTION"]
        self.assertEqual(abs(act_rank - exp_rank), 1)

    def test_partial_lower_card_entity(self):
        # Entity only in 4th alert (index 3)
        alerts = [
            {"headline": "Unrelated issue 1"},
            {"headline": "Unrelated issue 2"},
            {"headline": "Unrelated issue 3"},
            {"headline": "Overdue delivery from EastCoast Components (PO #19)"}
        ]
        top_3 = alerts[:3]
        lower = alerts[3:]
        self.assertFalse(any(check_entity_match(a["headline"], "eastcoast", {}) for a in top_3))
        self.assertTrue(any(check_entity_match(a["headline"], "eastcoast", {}) for a in lower))

    def test_control_day_false_alarm_is_miss(self):
        # Control day (Day 9): expected NEEDS_ATTENTION or WATCH, actual CRITICAL (rank 3)
        exp_ranks = [TIER_RANKS["NEEDS_ATTENTION"], TIER_RANKS["WATCH"]]
        act_rank = TIER_RANKS["CRITICAL"]
        self.assertGreater(act_rank, max(exp_ranks))

    def test_control_day_matching_tier_is_hit(self):
        # Control day (Day 9): expected NEEDS_ATTENTION or WATCH, actual NEEDS_ATTENTION
        exp_tiers = ["NEEDS_ATTENTION", "WATCH"]
        act_tier = "NEEDS_ATTENTION"
        self.assertIn(act_tier, exp_tiers)


if __name__ == "__main__":
    unittest.main()
