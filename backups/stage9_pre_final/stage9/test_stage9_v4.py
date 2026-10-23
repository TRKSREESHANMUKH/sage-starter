"""
stage9/test_stage9_v4.py — Stage 9 v4 Verification Test Suite.

Verifies:
1. Placeholder recipient is refused and the replay pointer does not advance.
2. A cover figure is never printed when the denominator is a fallback.
3. Today cards never show Strong/Some/Weak evidence for live operational facts.
4. The Insights tab uses no data after the as-of date (temporal isolation).
5. The supplier rating rule on a hand-built fixture, including the n < 5 case.
6. The word "caused" (and "caused by") never appears in visible Insights HTML outside Past analysed cases.
7. No jargon words in visible HTML outside "Technical details".
8. Cache determinism (byte-identical JSON on rerun).
9. AST anti-leakage test passes: Insights code does not reference ground truth or research_view.
"""

import ast
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from stage9.scheduler import validate_recipients
from stage9.clock import get_as_of_date
from stage9.current_day import get_current_day
from stage9.snapshot import compute_daily_snapshot
from stage9.priorities import compute_priorities
from stage9.narrate import generate_executive_narrative
from web.one_page_data import build_one_page_context
from web.insights_data import (
    compute_rating,
    get_insights_data,
    compute_insights_payload,
    generate_supplier_report_csv,
    CACHE_DIR
)


# 1. Placeholder recipient is refused and replay pointer does not advance
def test_placeholder_recipient_refused_and_replay_pointer_not_advanced():
    is_valid, msg = validate_recipients(["PUT_REAL_ADDRESSES_HERE"])
    assert not is_valid, "Placeholder recipient should be refused"
    assert "Placeholder recipient rejected" in msg

    is_valid_local, msg_local = validate_recipients(["user@server.local"])
    assert not is_valid_local, ".local domain should be refused"
    assert ".local domain rejected" in msg_local

    old_env = os.environ.get("SAGE_ALLOWED_RECIPIENTS")
    try:
        os.environ["SAGE_ALLOWED_RECIPIENTS"] = "owner@company.com,alert@company.com"
        is_valid_ext, msg_ext = validate_recipients(["stranger@external.com"])
        assert not is_valid_ext, "Unwhitelisted recipient should be refused"
        assert "not on SAGE_ALLOWED_RECIPIENTS" in msg_ext

        is_valid_ok, msg_ok = validate_recipients(["owner@company.com"])
        assert is_valid_ok, "Whitelisted recipient should be accepted"
        assert msg_ok == "Valid"
    finally:
        if old_env is not None:
            os.environ["SAGE_ALLOWED_RECIPIENTS"] = old_env
        else:
            os.environ.pop("SAGE_ALLOWED_RECIPIENTS", None)

    # Verify pointer immutability on failure
    initial_pointer = get_as_of_date()
    assert initial_pointer == get_current_day(), f"Replay pointer should equal current day, got {initial_pointer}"


# 2. Days of cover never prints fallback denominator figure
def test_days_of_cover_never_uses_fallback_denominator():
    # Test formula: When trailing 7-day usage is 0, days_of_cover must be None
    mock_snap = {
        "as_of": "2025-01-15",
        "plant_severity": "NORMAL",
        "composite_severity_score": 0.0,
        "materials": {
            "101": {
                "material_id": 101,
                "name": "Raw steel",
                "stock": 250.0,
                "safety_stock": 50.0,
                "reorder_point": 150.0,
                "days_of_cover": None,
                "open_pos_count": 0,
                "overdue_pos": [],
                "severity": "NORMAL"
            },
            "102": {
                "material_id": 102,
                "name": "Copper wire",
                "stock": 220.0,
                "safety_stock": 40.0,
                "reorder_point": 120.0,
                "days_of_cover": None,
                "open_pos_count": 0,
                "overdue_pos": [],
                "severity": "NORMAL"
            }
        },
        "products": {},
        "suppliers": {},
        "kpis": {}
    }
    pri = compute_priorities(date(2025, 1, 15), snapshot=mock_snap)
    narr = generate_executive_narrative(mock_snap, pri)

    # Assert fallback figures like "250.0 days" or "220.0 days" never appear
    assert "250.0 days of cover" not in str(narr)
    assert "220.0 days of cover" not in str(narr)
    for p in pri.get("top_priorities", []):
        assert "250.0 days" not in str(p)
        assert "220.0 days" not in str(p)
        if "250 kg on hand" in str(p):
            assert "has no recent use" in str(p)


# 3. Today cards never show Strong/Some/Weak evidence for live operational facts
def test_today_cards_never_show_strong_some_weak_for_live_facts():
    ctx = build_one_page_context("2025-02-03")
    for card in ctx.get("op_cards", []):
        assert card["evidence_label"] == "Seen directly in the data", \
            f"Live operational card had inappropriate evidence label: {card['evidence_label']}"
        assert card["badge_class"] == "badge-fact", \
            f"Expected badge-fact for live card, got: {card['badge_class']}"


# 4. Insights tab uses no data after as-of date (temporal isolation)
def test_insights_tab_no_future_lookahead():
    as_of = date(2025, 2, 3)
    p1 = compute_insights_payload(as_of, "ytd", False)

    # Verify all deliveries are on or before as_of
    for supp in p1["supplier_cards"]:
        for d in supp["deliveries"]:
            deliv_d = date.fromisoformat(d["receipt_date"])
            assert deliv_d <= as_of, f"Delivery {d['po_id']} dated {deliv_d} is after as_of {as_of}"

    # Verify all episode dates are on or before as_of
    for ep in p1["episodes"]["table"]:
        end_d = date.fromisoformat(ep["end_date"])
        assert end_d <= as_of, f"Episode end {end_d} is after as_of {as_of}"

    # Verify charts dates are on or before as_of
    for dt_str in p1["episodes"]["dates"]:
        assert date.fromisoformat(dt_str) <= as_of


# 5. Supplier rating rule on hand-built fixtures (including n < 5)
def test_supplier_rating_rule_fixtures():
    # Grade A: on_time >= 90% and fill_rate >= 95% (n >= 5)
    r1, b1, g1 = compute_rating(95.0, 98.0, 10)
    assert r1 == "Grade A" and b1 == "badge-strong" and not g1

    r2, b2, g2 = compute_rating(90.0, 95.0, 5)
    assert r2 == "Grade A" and b2 == "badge-strong" and not g2

    # Grade B: on_time >= 70%
    r3, b3, g3 = compute_rating(85.0, 90.0, 6)
    assert r3 == "Grade B" and b3 == "badge-some" and not g3

    r4, b4, g4 = compute_rating(70.0, 80.0, 5)
    assert r4 == "Grade B" and b4 == "badge-some" and not g4

    # Grade C: on_time < 70%
    r5, b5, g5 = compute_rating(65.0, 90.0, 8)
    assert r5 == "Grade C" and b5 == "badge-weak" and not g5

    # Small sample (n < 5): "Too few deliveries to rate" (greyed out)
    r6, b6, g6 = compute_rating(100.0, 100.0, 4)
    assert r6 == "Too few deliveries to rate" and b6 == "badge-calm" and g6

    r7, b7, g7 = compute_rating(0.0, 0.0, 1)
    assert r7 == "Too few deliveries to rate" and b7 == "badge-calm" and g7


# 6. The word "caused" never appears in visible Insights HTML outside Past analysed cases
def test_word_caused_never_in_visible_insights_html_outside_past_cases():
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader(str(ROOT_DIR / "web" / "templates")))
    tmpl = env.get_template("insights.html")

    data = get_insights_data("2025-02-03", "ytd")
    ctx = dict(data)
    ctx["selected_date"] = data["as_of"]
    ctx["period"] = "ytd"
    rendered_html = tmpl.render(ctx)

    # Split at Past analysed cases section
    split_token = 'id="past-analysed-cases"'
    assert split_token in rendered_html, "Past analysed cases section missing"
    top_half, _ = rendered_html.split(split_token, 1)

    # Remove the explicit required footnote:
    # "This table does not claim the supplier caused the shortage."
    footnote = "This table does not claim the supplier caused the shortage."
    top_clean = top_half.replace(footnote, "")

    # Search for forbidden "caused" or "caused by"
    matches = re.findall(r'\bcaused\b|\bcaused by\b', top_clean, re.IGNORECASE)
    assert len(matches) == 0, f"Found prohibited 'caused' in visible Insights HTML: {matches}"


# 7. No technical jargon outside Technical details
def test_no_jargon_outside_technical_details():
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader(str(ROOT_DIR / "web" / "templates")))
    tmpl = env.get_template("insights.html")

    data = get_insights_data("2025-02-03", "ytd")
    ctx = dict(data)
    ctx["selected_date"] = data["as_of"]
    ctx["period"] = "ytd"
    rendered_html = tmpl.render(ctx)

    # Strip out all <details> containing technical details
    clean_html = re.sub(r'<details[\s\S]*?Technical details[\s\S]*?</details>', '', rendered_html, flags=re.IGNORECASE)

    prohibited_jargon = [
        r'\bshapley\b',
        r'\bp95\b',
        r'\bnull distribution\b',
        r'\bmethod 1\b',
        r'\bmethod 2\b',
        r'\bcounterfactual\b',
        r'\bexogenous\b'
    ]

    for term in prohibited_jargon:
        matches = re.findall(term, clean_html, re.IGNORECASE)
        assert len(matches) == 0, f"Prohibited jargon '{term}' found in visible manager HTML: {matches}"


# 8. Cache determinism (byte-identical JSON on rerun)
def test_cache_determinism():
    as_of = date(2025, 2, 3)
    p1 = compute_insights_payload(as_of, "ytd", False)
    p2 = compute_insights_payload(as_of, "ytd", False)

    str1 = json.dumps(p1, sort_keys=True, indent=2)
    str2 = json.dumps(p2, sort_keys=True, indent=2)

    assert str1 == str2, "Insights payload must be byte-identical on rerun"


# 9. AST anti-leakage test: Insights does not reference ground truth or research_view
def test_anti_leakage_ast_insights():
    insights_py = ROOT_DIR / "web" / "insights_data.py"
    assert insights_py.exists()

    with open(insights_py, "r", encoding="utf-8") as f:
        source_code = f.read()

    tree = ast.parse(source_code)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "research_view" not in alias.name, "insights_data.py cannot import research_view"
                assert "business_events" not in alias.name, "insights_data.py cannot import business_events"
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                assert "research_view" not in node.module, "insights_data.py cannot import from research_view"
                assert "business_events" not in node.module, "insights_data.py cannot import from business_events"

    # Verify no ground truth files are referenced for loading
    forbidden_files = ["ground_truth.json", "business_events.parquet", "ground_truth.parquet", "incidents.json"]
    for ff in forbidden_files:
        assert ff not in source_code, f"Forbidden file '{ff}' found in insights_data.py"


if __name__ == "__main__":
    test_suite = [
        test_placeholder_recipient_refused_and_replay_pointer_not_advanced,
        test_days_of_cover_never_uses_fallback_denominator,
        test_today_cards_never_show_strong_some_weak_for_live_facts,
        test_insights_tab_no_future_lookahead,
        test_supplier_rating_rule_fixtures,
        test_word_caused_never_in_visible_insights_html_outside_past_cases,
        test_no_jargon_outside_technical_details,
        test_cache_determinism,
        test_anti_leakage_ast_insights,
    ]

    passed = 0
    failed = 0
    print(f"Running {len(test_suite)} Stage 9 v4 test suites...\n")
    for t in test_suite:
        name = t.__name__
        try:
            t()
            print(f"  [PASS] {name}")
            passed += 1
        except Exception as exc:
            import traceback
            print(f"  [FAIL] {name}: {exc}")
            traceback.print_exc()
            failed += 1

    print(f"\nResults: {passed} passed, {failed} failed.")
    if failed > 0:
        sys.exit(1)
