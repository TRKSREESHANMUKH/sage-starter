# SAGE Final Prompt — HANDOFF

## Status: COMPLETE — All Parts Complete & Verified Cleanly

Stages 1–8 strictly frozen. Main PostgreSQL database protected read-only (`SET default_transaction_read_only = on`). All figures traced to truth layer, manifest, or pre-registered model outputs. No live email sent.

---

## Final Prompt Execution Progress

### Part 0: Rules & Safeguards
- [x] **Pre-execution Backup**: Created `backups/stage9_pre_history/` containing `stage9/`, `web/`, `controller/`, `live/`, `demo_data/`, `reports/`, `stage10/`.
- [x] **Frozen Stages 1–8**: Fully preserved. No code changes to `stage1`..`stage8`, `stage7/FROZEN.json`, `stage8/FROZEN.json`.
- [x] **PostgreSQL Main Database**: Strictly read-only (`default_transaction_read_only = on`).
- [x] **Framing Sentence Verbatim**: Printed verbatim across all operational pages, modals, emails, 1-page PDFs, and reports:  
  *"SAGE performs controlled synthetic causal-attribution evaluation under an expert-defined causal model; it does not claim to prove real-world causality."*
- [x] **Zero Forbidden Tokens**: Zero paths, SQL, stack traces, `INC_` strings, "None", "NaN", or "undefined" on screen or user views.
- [x] **Mail Safety**: All test suites and `./verify_all.sh` force Dry-run mode. `sent_log.jsonl` SUCCESS_LIVE count verified unchanged.

### Part A: UI Changes (Today & Insights)
- [x] **A1. Baseline Notice Removed from Today/Insights**: The "Opening position set on 31 Dec 2025..." notice was removed from `home.html` and `insights.html`. Disclosed honestly on Method page (`method.html`) under "How the demo starts", generated from `demo_seed_manifest.json` (48 sales orders, 652 units, PO #18, opening inventory). "Cancelled at demo opening position" bucket preserved in Insights.
- [x] **A2. Top-Bar Day Dropdown Removed**: Removed `<select id="day-selector">` dropdown from `base.html`. Kept current day label, PDF/web download links, and controller link.
- [x] **A3. History and Key Events in Insights**:
  - "Year at a glance": Calendar heat grid of all 365 days colored by banner tier (Normal, Watch, Needs attention, Critical) with accessible labels and links to past days. Responsive wrapping without horizontal scroll.
  - "Key events": Chronological list of 75 disruption episodes derived from the product's daily status (grouped consecutive non-normal days and single-day events) with tier filters and "Open that day" links.
  - "View a past day": Date picker to `/?date=YYYY-MM-DD` rendering read-only past day view with clear banner and "Back to today". Future dates return status 400 with honest message: *"That day has not happened yet in this demo"*.
  - Persistent day index (`stage9/state/day_index.json`): Built in 123.28s (< 3 minutes) at reset; incrementally updated upon pack ingestion. Parity verified against 10 sample dates with 100% exact match. Sub-3-second render latency verified on Today (0.614s) and Insights (1.102s).
- [x] **A4. Compact Weekly Forecast Card on Today**:
  - "Next 7 days: expected new orders" card displaying horizon dates, shortage risk badge ("Low", "Medium", "High"), expected units, known due orders on the books, 12-week sparkline SVG, and Insights link.
  - 1-line email forward-look summary.
  - 1-page A4 PDF output strictly preserved (verified across 2025-12-31, 2026-01-01, 2026-01-07).

### Part B: Weekly Order Forecast & Scientific Benchmark
- [x] **B1. Pre-Registration**: Pre-registered protocol committed at `3e63717` in `stage10/prereg_forecast_v3.md` prior to model training.
- [x] **B2. Candidate Architecture Evaluation**:
  - H1 Cross-Validation ($n=21$ Sundays): Model 2 (Trailing 28d Mean x 7) selected with lowest CV WAPE (0.5455 / 45.5% accuracy, MAE 31.14 units).
  - Out-of-Sample H2 Walk-Forward Test ($n=25$ Sundays): Model 2 achieved 0.6474 WAPE (35.3% accuracy, MAE 31.10 units, Bias -2.42 units, MASE 0.766 vs naive baseline).
  - Rolling Daily Test ($n=177$ horizons): 0.6312 WAPE (36.9% accuracy, MAE 30.62 units).
  - Model serialized to `stage10/forecast/model.pkl` (SHA256: `a6b37c2e1558f1138a8e1165db602ec3ffc8de37a627fe01e6e37d1de427c6ab`).
- [x] **B3. Theoretical Irreducible Noise Floor Audit**:
  - `stage10/audit/noise_floor.py` simulated 100,000 weeks directly from true simulation parameters ($p=0.42$ Bernoulli order arrival, $\mathcal{U}[1,3]$ customers).
  - Proved theoretical Oracle minimum WAPE is **0.5034** (49.7% accuracy ceiling, 25.11 units MAE).
  - Deployed model operates within **0.1440 WAPE** of the theoretical noise limit (deployed WAPE 0.6474 vs Oracle 0.5034).
- [x] **B4. Forecast Report**: Complete report published in `stage10/FORECAST_REPORT.md`.

### Part C: Data & Narrative Consistency Fixes (C1–C11)
- [x] **C1**: PO #19 expected date set to 2026-01-02; 1d overdue on 2026-01-03.
- [x] **C2**: Receipt #26 mapped correctly to PO #20. Zero fake supplier prose.
- [x] **C3**: Zero `INC_` strings leak into templates or user views.
- [x] **C4**: 48 sales orders (652 units) in manifest, matching Postgres and `truth.json`.
- [x] **C5**: 2026 customer deliveries are 100% on time.
- [x] **C6**: Copper wire (Material 103) rendered strictly in meters.
- [x] **C7**: Idempotency in `get_sent_keys()` records only `SUCCESS_LIVE`, allowing live sends after dry runs.
- [x] **C8**: Prereg history and 10-day evaluation tables preserved.
- [x] **C9**: `git diff --stat 6ecff79 HEAD -- stage1..stage8` verified strictly 0.
- [x] **C10**: Causal tracing validated.
- [x] **C11**: Forecast shortage risk strictly bounded to "Low", "Medium", "High".
- [x] All verified via `stage9/test_consistency_fixes.py` (8/8 passed).

### Part D: Final Verification & Small Fixes Pass
- [x] **Forecast Card Layout & Positioning**:
  - Moved forecast card directly below the editorial summary paragraph and above the operational alert cards (`section-h`).
  - Numbers strip repositioned above the editorial summary paragraph as the top metric bar.
  - Shortage risk badge audited: formula `projected_weekly_buffer = fg_stock + 250 - due_k` was pre-registered in `stage10/prereg_forecast.md` for 1-day horizon, but NOT in `stage10/prereg_forecast_v3.md` (weekly protocol). Badge removed from `home.html` card.
  - Compact, mobile-safe layout verified; screenshots captured for Day 1 and Day 7 in `stage9/screenshots/today_day_1_*.png` and `today_day_7_*.png`.
- [x] **Raw Verification Outputs Printed**:
  - `stage10/audit/print_raw_verification.py` computes and prints full raw tables for C1–C11.
  - 2026 PO table (POs #19, #20, #22, GRs #23, #24, #25, #26; PO #26 confirmed as GR #26 misnomer; PO #19 expected date 2026-01-02 logged as post-hoc test calibration; deterministic generator re-run verified with 100% identical SHA256 hashes).
  - 2026 sales orders table (20/20 on-time shipments, 100% on-time delivery rate; backlogged orders on Day 7 and Day 9 reconciled in unfulfilled backlog bucket).
  - Manifest reconciliation: 48 orders / 652 units, stock balances 215 kg Steel / 204 kg Plastic / 184 m Copper; snapshot.py 630 overdue + 22 due today = 652 units.
  - Seasonality stress test attribution integrity: 96.7% (89/92 days); lag analysis sample sizes: $n=4$ (supplier delay to safety stock) and $n=1$ (stockout to backlog).
  - Three 10-day evaluation tables and honest scoring tally (v3 rules: 10/10 HIT; v1 original: 6/10 HIT).
  - History Explorer: Tier counts (Critical 154, Watch 49, Needs attention 38, Normal 124), first 20 key-event episodes, explanation of 75 episodes vs 10 incidents vs 215 calm days.
- [x] **Forecast Plain English Wording**:
  - Plain English wording implemented in `stage10/FORECAST_REPORT.md`, `web/templates/method.html`, and `web/templates/home.html`.
  - Stated: deployed model is Trailing 28-day Mean because it achieved lowest CV WAPE; count regression and gradient boosting did not beat it on this one-year simulated dataset; theoretical oracle ceiling WAPE 0.50 vs deployed 0.65; prediction range is wide.
  - "77.8% of the theoretical limit" phrasing completely removed across all files.
- [x] **Verification & Freezing**:
  - `verify_all.sh` executed cleanly (Exit code 0, all 13 suites passed).
  - `stage9/test_consistency_fixes.py` expanded with 5 new unit tests (history index, past-day no-look-ahead, notice removed, dropdown removed, forecast card wording) -> 13/13 tests passed.
  - `stage9/FROZEN.json` updated with latest SHA256 hashes for all 100 Stage 9 & Stage 10 files.
  - Stages 1–8 strictly frozen (`git diff --stat 6ecff79 HEAD -- stage1..stage8` is 0 diffs).
  - System left stopped, dry-run mode, current day `2025-12-31`.
- [x] Documentation updated: `DEMO.md`, `OWNER_CHECKLIST.md`, `stage10/KNOWN_ISSUES.md`, `stage10/PROJECT_SUMMARY.md`, `REQUIREMENTS_TRACE.md`.
- [x] Final screenshots regenerated in `analytics/screenshots/final/`.
- [x] Clean run of `./verify_all.sh` (100% pass, exit 0, zero live emails dispatched).
- [x] `stage9/FROZEN.json` updated with latest SHA256 hashes.

### Part E: Addendum Verification (Items 1–8)
- [x] **Item 1: Supplier Names Standardization**: Verified against PostgreSQL master `suppliers` table (ID 3: Global Polymers Co, ID 4: EastCoast Components, ID 5: Copper & Co; backup vendors ID 1: Sri Materials Pvt Ltd, ID 2: Bharat Steel Works). Eliminated all occurrences of "Apex Polymers" or "Metro Wiring Corp" across code, templates, and documentation.
- [x] **Item 2: Consolidated Sales Orders Table & Fulfillment Reconciliation**: Sourced all 29 sales orders requested Jan 1–10 (9 standing from 2025 = 109u backlog; 20 placed in 2026 = 20/20 on time, 100.0%). Reconciled Day 7 (14 orders / 168u backlog concept) vs live data (9 backorders, 109u). Defined "on time" on Method page in one concise sentence: *"An order is on time if and only if it is shipped complete on or before its customer-requested delivery date; unfulfilled orders and orders encountering stockout remain in open backlog and are classified as not on time."*
- [x] **Item 3: Multi-Version Ten-Day Side-by-Side Table**: Published side-by-side table (v1, v2, v3) in `README.md`, `DEMO.md`, and `web/templates/method.html` with honest scoring tally and explicit rehearsal disclaimer: *"Version 3 expectations were written after seeing results (rehearsal, not validation)."*
- [x] **Item 4: Historical Tier Counts & Episode Controls**: Deleted "0 false alarms on 215 calm days" claim everywhere. Replaced with real tier counts: 124 Normal (34.0%), 49 Watch (13.4%), 38 Needs attention (10.4%), 154 Critical (42.2%). Labelled Key Events as `(Newest First)`. Added UI toggle `<input type="checkbox" id="toggle-new-events"> Show only new events` in Insights.
- [x] **Item 5: Opening Position & Inventory Reconciliation**: Disclosed seed edits on Method page (adjustment #484 +206 kg steel to 215 kg, cancelled 48 orders / 652 units, cancelled PO #18 407 units). Reconciled Day 1 draft stock (420/310/250) vs verified closing stock (215/204/184).
- [x] **Item 6: Stress Test Integer Reporting**: Disclosed exact integer counts: 3 false attributions out of 92 Q4 calendar days (2 supplier, 1 machine; 89/92 = 96.7% preserved). Response lag sample sizes: $n=4$ (supplier delay to safety stock breach) and $n=1$ (stockout to backlog).
- [x] **Item 7: FORECAST_REPORT.md CV/TEST Labeling & 68.2% Sourcing**: Labeled all metrics as `[CV]`, `[TEST]`, or `[ORACLE]`. Sourced the 68.2% zero-order day figure from executed SQL query (116 active days, 249 zero-order days = 68.219%).
- [x] **Item 8: verify_all.sh Suite Counts & Step Evolution**: Added per-suite test/check counts (168 checks total). Documented 14 -> 13 step evolution (merging Playwright smoke UI and screenshot generator into Step 11). Added 4 new test suites to `stage9/test_consistency_fixes.py` (slim strip has no metrics, past-day no-lookahead, notice/dropdown removed, forecast v4 prereg).
- [x] **Final Verification & State**: All 13 steps passed cleanly (168 checks [100% PASS]). Live environment cleanly restored to 2025-12-31 in DRY-RUN mode. SAGE servers stopped.
- [x] Ready for final commit: `stage10 addendum verification`.
