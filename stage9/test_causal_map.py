"""
stage9/test_causal_map.py — Automated test for Part E (Causal Chain Map & Incident Log).
"""

from datetime import date
from pathlib import Path
import unittest

from stage9.causal_map import get_causal_chain_map, get_incident_log


class TestCausalMapAndIncidentLog(unittest.TestCase):
    def test_causal_chain_map_structure(self):
        # Test 2025-12-31 (baseline active day)
        cmap = get_causal_chain_map(date(2025, 12, 31))
        self.assertIn("has_active_chain", cmap)
        self.assertIn("one_line_text", cmap)
        self.assertIn("chains", cmap)
        self.assertTrue(cmap["has_active_chain"])
        self.assertGreaterEqual(len(cmap["chains"]), 1)

        first_chain = cmap["chains"][0]
        self.assertIn("tab_title", first_chain)
        self.assertIn("evidence_label", first_chain)
        self.assertIn(first_chain["evidence_label"], ["Seen end to end", "Partly seen", "No upstream explanation found"])
        self.assertEqual(len(first_chain["nodes"]), 4)

        node_titles = [n["title"] for n in first_chain["nodes"]]
        self.assertEqual(node_titles, [
            "SUPPLIER DELAY",
            "MATERIAL SHORTAGE",
            "PRODUCTION DELAY",
            "DELIVERY IMPACT"
        ])
        for n in first_chain["nodes"]:
            self.assertIn("subtext", n)
            self.assertIn("is_dashed", n)
            self.assertIn("has_evidence", n)

    def test_causal_chain_map_day_7(self):
        # Day 7 (2026-01-07): steel stockout and backorders
        cmap = get_causal_chain_map(date(2026, 1, 7))
        self.assertTrue(cmap["has_active_chain"])
        first_chain = cmap["chains"][0]
        self.assertEqual(first_chain["evidence_label"], "Seen end to end")
        self.assertEqual(cmap["one_line_text"], "Supplier delay > Material shortage > Production delay > Delivery impact")

    def test_incident_log_structure_and_ordering(self):
        incidents = get_incident_log(date(2025, 12, 31), limit=10)
        self.assertGreater(len(incidents), 0)
        self.assertLessEqual(len(incidents), 10)

        # Check newest first ordering
        for i in range(len(incidents) - 1):
            self.assertGreaterEqual(incidents[i]["date_iso"], incidents[i + 1]["date_iso"])

        for inc in incidents:
            self.assertIn("date_display", inc)
            self.assertIn("severity", inc)
            self.assertIn(inc["severity"], ["LOW", "MEDIUM", "HIGH"])
            self.assertIn("title", inc)
            self.assertIn(inc["title"], [
                "Overdue delivery",
                "Safety stock breach",
                "Production below plan",
                "Elevated demand intake",
                "Customer backlog",
                "Operational notice"
            ])
            self.assertIn("description", inc)

    def test_templates_integration(self):
        home_html = Path("web/templates/home.html").read_text(encoding="utf-8")
        self.assertIn("CAUSAL CHAIN MAP", home_html.upper())
        self.assertIn("Recent Incidents", home_html)
        self.assertIn("switchCausalTab", home_html)

        insights_html = Path("web/templates/insights.html").read_text(encoding="utf-8")
        self.assertIn("Incident Log", insights_html)
        self.assertIn("filterIncidentLog", insights_html)
        self.assertIn("preview-causal-box", insights_html)

    def test_render_email_one_line_chain(self):
        from stage9.render_email import render_nightly_digest
        res = render_nightly_digest(as_of=date(2025, 12, 31))
        subject, html, text_out = res[0], res[1], res[2]
        self.assertIn("Causal Chain", html)
        self.assertIn("Supplier delay > Material shortage > Production delay > Delivery impact", html)


if __name__ == "__main__":
    unittest.main()
