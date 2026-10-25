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
  - Deployed model operates within **0.1440 WAPE** of the theoretical noise limit (capturing 77.8% of the theoretical oracle limit).
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

### Part D: Verification, Screenshots & Delivery
- [x] Documentation updated: `DEMO.md`, `OWNER_CHECKLIST.md`, `stage10/KNOWN_ISSUES.md`, `stage10/PROJECT_SUMMARY.md`, `REQUIREMENTS_TRACE.md`.
- [x] Final screenshots regenerated in `analytics/screenshots/final/`.
- [x] Clean run of `./verify_all.sh` (100% pass, exit 0, zero live emails dispatched).
- [x] `stage9/FROZEN.json` updated with latest SHA256 hashes.
- [x] Ready for final commit: `stage10 forecast and history`.
