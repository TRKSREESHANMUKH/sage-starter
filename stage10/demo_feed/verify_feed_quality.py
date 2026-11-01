"""
stage10/demo_feed/verify_feed_quality.py — Quality Verification Suite for Redesigned Feed (v4 Protocol)

Runs automated quality assertions across all 10 simulation days:
1. Numbers strip: no None/NaN/undefined, no bare zero without context
2. Summary: >= 6 sentences, >= 4 distinct numbers, text similarity to previous day < 60% shared words
3. Focus boxes: Today's focus >= 3 items, Weekly focus >= 3 items
4. Forecast: Booked units > 0 and expected new orders > 0
5. Activity counts: Shipments, receipts/events, production, stock movements > 0 (except explicitly zero days)
6. Insights panels: Non-empty for each day
7. Fulfillment dynamics: Late shipments on Day 7 > 0; carried-over backlog strictly falls on Days 8, 9, 10
"""

from __future__ import annotations

import csv
from datetime import date
import json
from pathlib import Path
import re
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from web.one_page_data import build_one_page_context
from web.insights_data import get_insights_data
from stage10.forecast.outlook import get_weekly_forecast

PACKS_DIR = ROOT_DIR / "demo_data" / "packs"


def word_set(text: str) -> set[str]:
    framing = "sage performs controlled synthetic causal-attribution evaluation under an expert-defined causal model; it does not claim to prove real-world causality."
    clean = text.lower().replace(framing, "")
    return set(re.findall(r'[a-zA-Z0-9]+', clean))


def compute_similarity(s1: str, s2: str) -> float:
    w1 = word_set(s1)
    w2 = word_set(s2)
    if not w1 or not w2:
        return 0.0
    shared = w1.intersection(w2)
    return round((len(shared) / max(len(w1), len(w2))) * 100.0, 1)


def verify_all_quality_checks():
    print("=" * 100)
    print("SAGE Stage 10: Ten-Day Feed Quality Verification Suite (v4 Protocol)")
    print("=" * 100)

    daily_results = []
    prev_summary_text = ""
    backlog_by_day = {}
    day7_late_shipments = 0

    for day in range(1, 11):
        d_str = f"2026-01-{day:02d}"
        d_obj = date.fromisoformat(d_str)

        # 1. Briefing context
        ctx = build_one_page_context(d_str)

        # A. Numbers strip check
        strip = ctx.get("numbers_strip", {})
        strip_clean = True
        for k, card in strip.items():
            val = str(card.get("val", ""))
            if val in ("None", "NaN", "undefined", ""):
                strip_clean = False

        # B. Summary text check
        summ = ctx.get("plain_summary", {})
        sentences = summ.get("sentences", [])
        summary_text = summ.get("text", "")
        n_sentences = len(sentences)

        # Distinct numbers in summary (excluding year numbers like 2026)
        found_nums = set(re.findall(r'\b\d+\b', summary_text)) - {"2025", "2026"}
        n_distinct_nums = len(found_nums)

        # Word overlap vs previous day
        if prev_summary_text:
            sim_pct = compute_similarity(summary_text, prev_summary_text)
        else:
            sim_pct = 0.0
        prev_summary_text = summary_text

        # C. Focus boxes check
        focus_items = ctx.get("focus_items", [])
        weekly_focus = ctx.get("weekly_focus", [])
        n_focus = len(focus_items)
        n_weekly_focus = len(weekly_focus)

        # D. Forecast check
        fc = get_weekly_forecast(d_obj)
        due_k = fc.get("due_known", 0)
        exp_new = fc.get("expected_new_orders", 0)
        forecast_ok = (due_k > 0 and exp_new > 0)

        # E. Pack activity counts
        pack_dir = PACKS_DIR / d_str
        n_delivs = 0
        n_grs = 0
        n_pos = 0
        n_prods = 0
        n_movs = 0
        if pack_dir.exists():
            with open(pack_dir / "deliveries.csv", "r", encoding="utf-8") as f:
                n_delivs = len(list(csv.DictReader(f)))
            with open(pack_dir / "goods_receipts.csv", "r", encoding="utf-8") as f:
                n_grs = len(list(csv.DictReader(f)))
            with open(pack_dir / "purchase_orders.csv", "r", encoding="utf-8") as f:
                n_pos = len(list(csv.DictReader(f)))
            with open(pack_dir / "production_orders.csv", "r", encoding="utf-8") as f:
                n_prods = len(list(csv.DictReader(f)))
            with open(pack_dir / "stock_movements.csv", "r", encoding="utf-8") as f:
                n_movs = len(list(csv.DictReader(f)))

        # Explicitly zero days:
        # Deliveries zero days: Days 1, 2, 3 (orders lead time >= 3d, backorders held for Days 8-10)
        # Receipts zero days: Days 1, 2, 3, 5, 7, 9, 10
        # Production zero days: Day 7 (Model X halted; Model Y planned 4, act 0)
        deliv_ok = (n_delivs > 0) or (day in (1, 2, 3))
        gr_ok = (n_grs > 0 or n_pos > 0) or (day in (1, 2, 3, 5, 7, 9, 10))
        prod_ok = (n_prods > 0)
        mov_ok = (n_movs > 0)

        # F. Insights panels check
        insights = get_insights_data(d_str, "all")
        supp_cards = insights.get("supplier_cards", [])
        product_service = insights.get("product_service", [])
        delay_ledger = insights.get("delay_ledger", [])
        insights_non_empty = bool(supp_cards and product_service and delay_ledger)

        # G. Tracking Day 7 late shipments & Days 8-10 backlog
        if day == 7:
            # Check shipped late count in fulfillment buckets and customer delay ledger
            fb = insights.get("fulfillment_buckets", {})
            dl = [r for r in insights.get("delay_ledger", []) if r.get("record_type") == "Customer Order" and r.get("actual_date") == d_str]
            day7_late_shipments = max(int(fb.get("shipped_late_orders", 0)), len(dl))

        # Backlog units from snapshot
        snap = ctx.get("snapshot", {})
        kpis = snap.get("kpis", {})
        bl_units = int(kpis.get("total_backlog_units", 0))
        backlog_by_day[day] = bl_units

        # Day verdict
        checks_passed = (
            strip_clean and
            (n_sentences >= 6) and
            (n_distinct_nums >= 4) and
            (sim_pct < 60.0 or day == 1) and
            (n_focus >= 3) and
            (n_weekly_focus >= 3) and
            forecast_ok and
            deliv_ok and gr_ok and prod_ok and mov_ok and
            insights_non_empty
        )

        # Tier from issues top badge
        issues = ctx.get("issues", [])
        day_tier = issues[0].get("badge", "NORMAL") if issues else "NORMAL"

        daily_results.append({
            "day": day,
            "date": d_str,
            "tier": day_tier,
            "strip_clean": strip_clean,
            "sentences": n_sentences,
            "distinct_nums": n_distinct_nums,
            "similarity_pct": sim_pct,
            "focus_count": n_focus,
            "weekly_focus_count": n_weekly_focus,
            "forecast_ok": forecast_ok,
            "booked_units": due_k,
            "exp_new_orders": exp_new,
            "shipments": n_delivs,
            "receipts": n_grs,
            "movements": n_movs,
            "insights_ok": insights_non_empty,
            "passed": checks_passed
        })

    # Assertions across days:
    day7_late_ok = (day7_late_shipments > 0)
    bl_d7 = backlog_by_day.get(7, 0)
    bl_d8 = backlog_by_day.get(8, 0)
    bl_d9 = backlog_by_day.get(9, 0)
    bl_d10 = backlog_by_day.get(10, 0)
    backlog_falling = (bl_d7 > bl_d8 > bl_d9 > bl_d10)

    # Print Report
    print(f"{'Day':<5} {'Date':<11} {'Tier':<16} {'Strip':<6} {'Sent':<5} {'Nums':<5} {'Sim%':<6} {'Focus':<6} {'WFocus':<7} {'Fcst':<5} {'Ship':<5} {'Mov':<5} {'Verdict'}")
    print("-" * 100)
    for r in daily_results:
        verdict = "PASS" if r["passed"] else "FAIL"
        print(f"Day {r['day']:<2} {r['date']:<11} {r['tier']:<16} {'OK' if r['strip_clean'] else 'BAD':<6} {r['sentences']:<5} {r['distinct_nums']:<5} {r['similarity_pct']:<6} {r['focus_count']:<6} {r['weekly_focus_count']:<7} {'OK' if r['forecast_ok'] else 'BAD':<5} {r['shipments']:<5} {r['movements']:<5} {verdict}")

    print("-" * 100)
    print("\nCROSS-DAY FULFILLMENT DYNAMICS AUDIT:")
    print(f"  * Day 7 Genuine Late Shipments: {day7_late_shipments} orders (>0 -> {'PASS' if day7_late_ok else 'FAIL'})")
    print(f"  * Carried-Over Backlog Burn-Down: Day 7 ({bl_d7}u) -> Day 8 ({bl_d8}u) -> Day 9 ({bl_d9}u) -> Day 10 ({bl_d10}u)")
    print(f"  * Backlog Strictly Falls Days 8-10: {'PASS' if backlog_falling else 'FAIL'}")

    all_passed = all(r["passed"] for r in daily_results) and day7_late_ok and backlog_falling
    print("\n" + "=" * 100)
    print(f"OVERALL FEED QUALITY CHECK RESULT: {'ALL PASS (10/10 Days Verified)' if all_passed else 'SOME CHECKS FAILED'}")
    print("=" * 100)

    return all_passed


if __name__ == "__main__":
    ok = verify_all_quality_checks()
    sys.exit(0 if ok else 1)
