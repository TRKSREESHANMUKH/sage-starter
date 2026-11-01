"""
stage9/test_feed_showpiece.py — Test for Part D (Live Feed Stepper & Telemetry).
"""

import unittest
from stage9.pipeline_runner import PIPELINE_STEPS, get_pipeline_state


class TestFeedShowpiece(unittest.TestCase):
    def test_pipeline_steps_count_and_names(self):
        self.assertEqual(len(PIPELINE_STEPS), 9)
        expected = [
            "Validate pack",
            "Ingest ERP events",
            "Material balance check",
            "BOM explosion",
            "Production reconciliation",
            "Backlog calculation",
            "Stage 7 GCM fit",
            "Stage 8 Narration",
            "Daily brief render"
        ]
        self.assertEqual(PIPELINE_STEPS, expected)

    def test_get_pipeline_state_structure(self):
        state = get_pipeline_state()
        self.assertIn("active", state)
        self.assertIn("steps", state)
        self.assertEqual(len(state["steps"]), 9)
        for st in state["steps"]:
            self.assertIn("name", st)
            self.assertIn("status", st)
            self.assertIn("elapsed_ms", st)
        self.assertIn("dag_active", state)

    def test_controller_dashboard_template_contains_stepper_and_dag(self):
        from pathlib import Path
        tmpl = Path("controller/templates/dashboard.html").read_text(encoding="utf-8")
        self.assertIn("live-stepper-box", tmpl)
        self.assertIn("mini-causal-dag", tmpl)
        self.assertIn("dag-node-po", tmpl)
        self.assertIn("dag-node-stock", tmpl)
        self.assertIn("dag-node-shortfall", tmpl)
        self.assertIn("dag-node-backorder", tmpl)
        self.assertIn("/ctrl/api/feed-next-day/progress", tmpl)


if __name__ == "__main__":
    unittest.main()
