"""
stage10/list_tests.py — Generates the complete, structured test list for SAGE.
Used by `./verify_all.sh --list`.

Prints:
- Every test ID by suite
- Baseline status ([BASELINE] or [NEW])
- Per-suite counts
- Grand total in a single unit ("checks")
"""

from __future__ import annotations
import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

def build_test_inventory():
    inventory = []

    # Suite 1: Frozen Stage Hashes (55 checks)
    with open(ROOT_DIR / "stage9" / "baseline_hashes.json", "r", encoding="utf-8") as f:
        baseline_hashes = json.load(f)
    s1_tests = []
    for i, p in enumerate(sorted(baseline_hashes.keys()), 1):
        s1_tests.append((f"FROZEN_{i:03d}", f"Frozen baseline hash for {p}", "BASELINE"))
    inventory.append(("Suite 1: Frozen Stage Hashes & Baseline Integrity", s1_tests))

    # Suite 2: Truth Layer Dual-Method Cross-Check (1 check)
    s2_tests = [
        ("TRUTH_CROSS_CHECK", "Dual-method cross-check of on-time orders (Method 1 == Method 2)", "BASELINE")
    ]
    inventory.append(("Suite 2: Truth Layer Dual-Method Cross-Check", s2_tests))

    # Suite 3: Page-vs-Truth Integrity (3 checks)
    s3_tests = [
        ("TEST_INSIGHTS_TRUTH_METRICS", "Insights data metrics match truth layer exactly", "BASELINE"),
        ("TEST_INSIGHTS_TRUTH_PAGE", "Page-vs-truth rendered DOM elements match truth values", "BASELINE"),
        ("TEST_INSIGHTS_TRUTH_CONSISTENCY", "Dual-method cross-check consistency across pages", "BASELINE"),
    ]
    inventory.append(("Suite 3: Page-vs-Truth Verification Suite", s3_tests))

    # Suite 4: Forensic Audit Suite (5 checks)
    s4_tests = [
        ("AUDIT_ORDERS", "Sales orders audit across full history", "BASELINE"),
        ("AUDIT_R5_SOURCING", "Supplier sourcing behavior and switch logic audit", "BASELINE"),
        ("AUDIT_METRICS", "Comprehensive KPI metric calculations audit", "BASELINE"),
        ("AUDIT_GATE_A_FULL", "Gate A full verification and forensic reconciliation", "BASELINE"),
        ("AUDIT_RECONCILE_R", "Reconciliation audit of R-records vs database tables", "BASELINE"),
    ]
    inventory.append(("Suite 4: Forensic Audit Suite", s4_tests))

    # Suite 5: Security & Hygiene Guards (2 checks)
    s5_tests = [
        ("GUARD_FORBIDDEN_LITERALS", "Scan for forbidden marketing and dummy strings (0 found)", "BASELINE"),
        ("GUARD_DEFAULT_TOKENS", "Scan for unrotated default security tokens outside backups", "BASELINE"),
    ]
    inventory.append(("Suite 5: Security & Hygiene Guards", s5_tests))

    # Suite 6: Mail Safety & Scheduler Proof (6 checks)
    s6_tests = [
        ("MAIL_SAFETY_PERSISTED_LIVE", "Persisted Live mode without flag forces dry-run (0 SMTP calls)", "BASELINE"),
        ("MAIL_SAFETY_LIVE_FLAG", "Live flag produces exactly one SMTP call (mocked)", "BASELINE"),
        ("MAIL_SAFETY_IDEMPOTENCY", "Scheduled send twice on same date skips second send", "BASELINE"),
        ("MAIL_SAFETY_REFUSALS", "Placeholder and unapproved recipients rejected safely", "BASELINE"),
        ("MAIL_SEND_CHECK_DRY_RUN", "Dry-run send execution check via stage9.send_check", "BASELINE"),
        ("SCHEDULER_PROOF_CADENCE", "Scheduler proof verifies Asia/Kolkata 20:00 cadence", "BASELINE"),
    ]
    inventory.append(("Suite 6: Mail Safety & Scheduler Proof", s6_tests))

    # Suite 7: Multi-Date Reconciliation Suite (21 checks)
    s7_tests = []
    for d in range(1, 22):
        s7_tests.append((f"RECONCILE_DATE_{d:02d}", f"Forensic reconciliation assertion for checkpoint date {d:02d}", "BASELINE"))
    inventory.append(("Suite 7: Multi-Date Forensic Reconciliation Suite", s7_tests))

    # Suite 8: Scoring Determinism, Weekly Outlook & Consistency Suite (34 checks: 12 baseline + 22 new)
    s8_tests = [
        # test_score.py (5 baseline)
        ("SCORE_HIT_TIER_TOP3", "HIT: tier matches and scripted entity in top-3 alerts", "BASELINE"),
        ("SCORE_PARTIAL_TIER_OFF1", "PARTIAL: entity in top-3 alerts but tier off by one", "BASELINE"),
        ("SCORE_PARTIAL_LOWER_CARD", "PARTIAL: scripted entity found in lower card (rank > 3)", "BASELINE"),
        ("SCORE_MISS_FALSE_ALARM", "MISS: control day banner tier above expected tier", "BASELINE"),
        ("SCORE_HIT_CONTROL_MATCH", "HIT: control day banner tier matches expected tier", "BASELINE"),
        # test_outlook.py (7 baseline)
        ("OUTLOOK_STRUCTURE", "Weekly outlook dictionary returns all required forecast fields", "BASELINE"),
        ("OUTLOOK_PAST_DAY_FLAG", "Past day forecast strictly uses past-day stored snapshot", "BASELINE"),
        ("OUTLOOK_STORED_ACCURACY", "Stored weekly forecast values match evaluation dataset", "BASELINE"),
        ("OUTLOOK_SPARKLINE_SVG", "SVG mini-sparkline generates valid SVG tags and coordinates", "BASELINE"),
        ("OUTLOOK_CACHE_CLEAR", "Outlook cache invalidation operates correctly", "BASELINE"),
        ("OUTLOOK_ZERO_LOOKAHEAD", "Weekly outlook enforces zero look-ahead contract", "BASELINE"),
        ("OUTLOOK_FRAMING_SENTENCE", "Mandatory research framing sentence attached to outlook", "BASELINE"),
        # test_consistency_fixes.py (22 new)
        ("C01_STEEL_PO19_EXP_DATE", "PO #19 expected date is 2026-01-02 (overdue Day 3)", "NEW"),
        ("C02_RECEIPTS_HAS_PO_ID", "Receipts today includes valid PO ID avoiding receipt confusion", "NEW"),
        ("C03_ZERO_INC_LEAKAGE", "Zero INC_ tokens leak into user-facing HTML, alerts, or emails", "NEW"),
        ("C04_MANIFEST_48_CANCELLED", "48 unfulfilled customer orders (652 units) confirmed cancelled in manifest", "NEW"),
        ("C06_COPPER_WIRE_METERS", "Copper wire inventory units rendered strictly as meters", "NEW"),
        ("C07_IDEMPOTENCY_LIVE_ONLY", "Idempotency in sent_log only records SUCCESS_LIVE; dry run never blocks", "NEW"),
        ("C09_FREEZE_ZERO_DIFF", "Commit 6ecff79 baseline freeze has 0 diffs across stages 1..8", "NEW"),
        ("C11_OUTLOOK_SHORTAGE_RISK", "Forecast shortage risk wording strictly Low, Medium, High", "NEW"),
        ("HISTORY_INDEX_STRUCTURE", "History day_index covers 365+ days and all 4 banner tiers", "NEW"),
        ("PAST_DAY_NO_LOOK_AHEAD", "Past day snapshot strictly uses data on or before selected date", "NEW"),
        ("BASELINE_NOTICE_REMOVED", "Demo Baseline Notice removed from Today page", "NEW"),
        ("DROPDOWN_SELECTOR_REMOVED", "Day-selector dropdown removed from Today page top bar", "NEW"),
        ("FORECAST_CARD_SLIM_LAYOUT", "Slim strip on Today has no WAPE/accuracy/MAE/model name and no shortage badge", "NEW"),
        ("SLIM_STRIP_NO_UNDEFINED", "Numbers strip has no None, NaN, or undefined values", "NEW"),
        ("FORECAST_V4_PREREG_EXISTS", "prereg_forecast_v4.md exists and contains framing and 68.2% query", "NEW"),
        ("METHOD_PAGE_DISCLOSURES", "Method page contains rehearsal disclosure, on-time definition, stress counts", "NEW"),
        ("SUPPLIER_NAMES_SOURCE_OF_TRUTH", "Zero occurrences of legacy placeholder supplier names across codebase", "NEW"),
        ("FACTS_VS_PAGES_MATCH", "DEMO_FACTS.json matches pages (31 SOs, Day 1 stock, Day 7 backlog)", "NEW"),
        ("ONE_OVERDUE_RULE_STRICT", "Overdue definition strictly requested_delivery_date < as_of", "NEW"),
        ("FORECAST_PREREG_ORDERING", "Pre-registration commit strictly precedes evaluation code commit", "NEW"),
        ("EPISODE_TOGGLE_FILTER", "#toggle-new-events checkbox and filtering logic exist in insights.html", "NEW"),
        ("MAIL_SAFETY_ZERO_REAL_SMTP", "Test harness enforces mock SMTP and dry-run safety", "NEW"),
    ]
    inventory.append(("Suite 8: Scoring Determinism, Weekly Outlook & Consistency Suite", s8_tests))

    # Suite 9: Comprehensive Stage 9 Test Suite (67 checks)
    with open(ROOT_DIR / "stage9" / "state" / "test_final_results.json", "r", encoding="utf-8") as f:
        s9_res = json.load(f).get("results", [])
    s9_tests = []
    for r in s9_res:
        t_id = f"STAGE9_{r['id']}_{r['name'][:25].replace(' ', '_').upper()}"
        s9_tests.append((t_id, r["name"], "BASELINE"))
    inventory.append(("Suite 9: Comprehensive Stage 9 Test Suite (Part G & Gate B)", s9_tests))

    # Suite 10: Server Startup & 127.0.0.1 Binding (2 checks)
    s10_tests = [
        ("BINDING_VIEWER_PORT_8000", "Viewer server bound strictly to 127.0.0.1:8000 (localhost only)", "BASELINE"),
        ("BINDING_CONTROLLER_PORT_8001", "Controller server bound strictly to 127.0.0.1:8001 (localhost only)", "BASELINE"),
    ]
    inventory.append(("Suite 10: Server Startup & 127.0.0.1 Localhost Binding Check", s10_tests))

    # Suite 11: Playwright Smoke UI Suite (9 checks)
    s11_tests = [
        ("SMOKE_01_VIEWER_HOME", "Viewer Home page loads with valid framing and no forbidden tokens", "BASELINE"),
        ("SMOKE_02_VIEWER_2025_03_01", "Viewer past day 2025-03-01 loads with 100.0% on-time & 4 deliveries", "BASELINE"),
        ("SMOKE_03_VIEWER_2025_12_31", "Viewer baseline 2025-12-31 reflects 78.3% on-time and PO #18 stuck", "BASELINE"),
        ("SMOKE_04_VIEWER_NAV_EXPANDERS", "Viewer tab navigation and expanders toggle cleanly; episode filter works", "BASELINE"),
        ("SMOKE_05_CONTROLLER_LOGIN", "Controller login with operator token succeeds with framing verified", "BASELINE"),
        ("SMOKE_06_CONTROLLER_PREVIEW_TODAY", "Controller preview today renders in <5s with framing & owner email", "BASELINE"),
        ("SMOKE_07_CONTROLLER_SEND_DRY_RUN", "Controller send report (dry-run) adds sent_log entry with banner", "BASELINE"),
        ("SMOKE_08_CONTROLLER_PREVIEW_PAST_DAY", "Controller past-day preview renders March 1 data cleanly", "BASELINE"),
        ("SMOKE_09_CONTROLLER_RESET_DEMO", "Controller demo reset cleanly restores live DB to 2025-12-31", "BASELINE"),
    ]
    inventory.append(("Suite 11: Playwright Smoke UI Suite", s11_tests))

    # Suite 12: Ten-Day Demo Feed Rehearsal & Scoring (10 checks: 1 baseline + 9 new)
    s12_tests = [
        ("REHEARSAL_DAY_01", "Day 1 (2026-01-01) feed ingestion & deterministic scoring", "BASELINE"),
        ("REHEARSAL_DAY_02", "Day 2 (2026-01-02) feed ingestion & deterministic scoring", "NEW"),
        ("REHEARSAL_DAY_03", "Day 3 (2026-01-03) feed ingestion & deterministic scoring", "NEW"),
        ("REHEARSAL_DAY_04", "Day 4 (2026-01-04) feed ingestion & deterministic scoring", "NEW"),
        ("REHEARSAL_DAY_05", "Day 5 (2026-01-05) feed ingestion & deterministic scoring", "NEW"),
        ("REHEARSAL_DAY_06", "Day 6 (2026-01-06) feed ingestion & deterministic scoring", "NEW"),
        ("REHEARSAL_DAY_07", "Day 7 (2026-01-07) feed ingestion & deterministic scoring", "NEW"),
        ("REHEARSAL_DAY_08", "Day 8 (2026-01-08) feed ingestion & deterministic scoring", "NEW"),
        ("REHEARSAL_DAY_09", "Day 9 (2026-01-09) feed ingestion & deterministic scoring", "NEW"),
        ("REHEARSAL_DAY_10", "Day 10 (2026-01-10) feed ingestion & deterministic scoring", "NEW"),
    ]
    inventory.append(("Suite 12: Ten-Day Demo Feed Rehearsal & Scoring", s12_tests))

    # Suite 13: Safety Reset & Cleanup (2 checks)
    s13_tests = [
        ("SAFETY_RESET_DAY_0", "Live environment cleanly restored to Day 0 (2025-12-31)", "BASELINE"),
        ("SAFETY_ZERO_LIVE_SENDS", "Zero live emails sent during verification (sent_log unchanged)", "BASELINE"),
    ]
    inventory.append(("Suite 13: Final Reset & Safety Verification", s13_tests))

    return inventory

def main():
    inventory = build_test_inventory()
    grand_total = 0
    baseline_total = 0
    new_total = 0

    print("=" * 80)
    print("SAGE UNIFIED VERIFICATION SUITE — COMPLETE TEST LIST (--list)")
    print("=" * 80)
    print("All items unified under ONE metric unit: 'checks'")
    print("-" * 80)

    for suite_name, tests in inventory:
        suite_baseline = sum(1 for _, _, tag in tests if tag == "BASELINE")
        suite_new = sum(1 for _, _, tag in tests if tag == "NEW")
        suite_total = len(tests)
        grand_total += suite_total
        baseline_total += suite_baseline
        new_total += suite_new

        print(f"\n{suite_name} ({suite_total} checks: {suite_baseline} baseline, {suite_new} new)")
        print("-" * 80)
        for t_id, desc, tag in tests:
            print(f"  [{tag:8}] {t_id:<36} {desc}")

    print("\n" + "=" * 80)
    print("VERIFICATION SUITE SUMMARY BY THE NUMBERS")
    print("=" * 80)
    for suite_name, tests in inventory:
        print(f"  {suite_name:<55} : {len(tests):3d} checks")
    print("-" * 80)
    print(f"  BASELINE CHECKS (Commit 66e4b85 baseline)        : {baseline_total:3d} checks")
    print(f"  NEW STAGE 10 VERIFICATION CHECKS                 : {new_total:3d} checks")
    print(f"  GRAND TOTAL UNIFIED VERIFICATION CHECKS          : {grand_total:3d} checks")
    print("=" * 80)

if __name__ == "__main__":
    main()
