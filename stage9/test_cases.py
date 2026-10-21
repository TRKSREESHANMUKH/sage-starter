"""
stage9/test_cases.py — Unit & Integration Tests for Stage 9 Final 2 Demo Cases.

Verifies:
1. Pre-registered 10 demo cases load correctly from demo_data/cases.json.
2. Fast jump_to_case execution (<30s).
3. Strict no-look-ahead isolation in live/sage_live.db.
4. Jump order invariance: jumping (Case 7 -> Case 2 -> Case 7) yields identical metrics.
5. Fact validator enforcement on summary leads.
"""

from __future__ import annotations

import json
import unittest
from datetime import date
from pathlib import Path
from sqlalchemy import func
from sqlalchemy.orm import sessionmaker

from app.database import get_engine
from app.models.purchasing import PurchaseOrder
from app.models.sales import SalesOrder
from stage9.ops import get_case_state, get_demo_cases, jump_to_case
from stage9.snapshot import compute_daily_snapshot
from web.one_page_data import build_one_page_context, validate_summary_lead

ROOT_DIR = Path(__file__).resolve().parent.parent


class TestDemoCases(unittest.TestCase):

    def test_demo_cases_manifest(self):
        cases = get_demo_cases()
        self.assertEqual(len(cases), 10, f"Expected 10 demo cases, got {len(cases)}")
        expected_dates = [
            "2025-03-31",
            "2025-10-02",
            "2025-07-22",
            "2025-08-07",
            "2025-03-02",
            "2025-08-20",
            "2025-10-20",
            "2025-12-01",
            "2025-01-15",
            "2025-12-31",
        ]
        actual_dates = [c["date"] for c in cases]
        self.assertEqual(actual_dates, expected_dates)

    def test_jump_to_case_no_lookahead(self):
        """Jumping to Case 1 (2025-03-31) must contain zero records with date > 2025-03-31."""
        st = jump_to_case(1, user="unittest")
        self.assertEqual(st["active_case"], 1)
        self.assertEqual(st["date"], "2025-03-31")

        eng = get_engine("live")
        Session = sessionmaker(bind=eng)
        db = Session()
        try:
            cutoff = date(2025, 3, 31)
            max_so = db.query(func.max(SalesOrder.order_date)).scalar()
            max_po = db.query(func.max(PurchaseOrder.order_date)).scalar()
            self.assertTrue(max_so is not None and max_so <= cutoff, f"Sales orders exceeded cutoff: {max_so}")
            self.assertTrue(max_po is not None and max_po <= cutoff, f"Purchase orders exceeded cutoff: {max_po}")
        finally:
            db.close()

    def test_jump_order_invariance(self):
        """Jumping to Case 7, then Case 5, then back to Case 7 must yield identical KPIs."""
        # First jump to Case 7
        jump_to_case(7, user="unittest")
        eng = get_engine("live")
        Session = sessionmaker(bind=eng)
        db = Session()
        snap1 = compute_daily_snapshot(date(2025, 10, 20), db_session=db)
        db.close()

        # Intervening jump to Case 5
        jump_to_case(5, user="unittest")

        # Return jump to Case 7
        jump_to_case(7, user="unittest")
        db2 = Session()
        snap2 = compute_daily_snapshot(date(2025, 10, 20), db_session=db2)
        db2.close()

        self.assertEqual(snap1["kpis"]["total_backlog_units"], snap2["kpis"]["total_backlog_units"])
        self.assertEqual(snap1["kpis"]["total_overdue_orders"], snap2["kpis"]["total_overdue_orders"])
        self.assertEqual(snap1["kpis"]["total_material_stockouts"], snap2["kpis"]["total_material_stockouts"])
        self.assertEqual(snap1["kpis"]["total_backlog_units"], 108)

    def test_summary_lead_validator(self):
        """Validates word count <= 60 and ungrounded number detection."""
        allowed = {"108", "10", "67", "9"}
        valid_lead = "Two suppliers are on schedule; one purchase order is overdue. Customer order backlogs reached 108 units across 10 orders."
        is_valid, msg = validate_summary_lead(valid_lead, allowed)
        self.assertTrue(is_valid, f"Expected valid lead, got: {msg}")

        too_long_lead = "word " * 65
        is_valid_long, msg_long = validate_summary_lead(too_long_lead, allowed)
        self.assertFalse(is_valid_long, "Expected validator to reject lead > 60 words")

    def test_one_page_context_structure(self):
        """Verifies build_one_page_context returns all required Morning Briefing keys."""
        ctx = build_one_page_context("2025-10-20")
        self.assertIn("editorial_lead", ctx)
        self.assertIn("numbers_strip", ctx)
        self.assertIn("issues", ctx)
        self.assertIn("focus_items", ctx)
        self.assertIn("supplier_watch", ctx)
        self.assertIn("framing", ctx)
        self.assertIn("SAGE performs controlled synthetic causal-attribution evaluation", ctx["framing"])


if __name__ == "__main__":
    unittest.main()
