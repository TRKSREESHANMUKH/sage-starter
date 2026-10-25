# SAGE Combined Final — HANDOFF

## Status: IN PROGRESS — Phase 1 Complete, Entering Phase 2

Stages 1–8 strictly frozen. Main PostgreSQL database protected read-only (`SET default_transaction_read_only = on`). All figures traced to truth layer. No live email sent.

---

## Combined Final Prompt — Execution Progress
- [x] **Pre-execution Backup**: Created `backups/stage9_pre_forecast/`
- [x] **Phase 1 — Close Evidence Gaps (Raw Output Verification)**:
  - 1. Mocked-SMTP tests: verified persisted Live + no `--live` = 0 calls; `--live` = 1 call; idempotency on same date/recipient.
  - 2. Insights tile table (live HTML vs truth) for 2025-12-31 (78.3%) and 2026-01-09 (76.2%), 48 cancelled orders bucket.
  - 3. Manifest audit: 8 vs 48 orders explained, notice text generated, SO #223 unfulfilled on 2025-12-31 (630 vs 652 units / 47 vs 48 orders) documented with unit tests.
  - 4. Frozen baseline: `stage9/baseline_hashes.json` git provenance confirmed, all 55 source files match baseline, Stage 7 & 8 hashes match byte-for-byte.
  - 5. Prereg history: v1/v2/v3 expected tiers, 3 ten-day tables, v1 scoring tally, Day 5 capacity alert verified in Top 3, daily material stock levels & active PO schedules.
  - 6. Verbatim executive summaries: Day 1, 3, 7, 9 with word counts and fact mappings.
  - 7. `verify_all.sh`: per-suite breakdown table strictly summing to 186 items across 14 steps.
  - 8. Screenshots & tokens hygiene: zero forbidden default tokens outside backups, `git ls-files` sensitive check clean (`.env.example` only).
  - 9. Scheduler proof: temporary schedule (+1m prepare, +2m send), scheduled prepare and dry-run send entries logged, controller restart between prepare and send handled idempotently, real schedule restored (19:45/20:00), instructions added to `OWNER_CHECKLIST.md`.
- [x] **Phase 2 — Report Parameters**:
  - Documented parameter rules & thresholds in `stage10/REPORT_PARAMETERS.md` across 5 groups (alert prioritization, root-cause tracing, narrative generation, tier assignment, stock/capacity thresholds).
  - Added "How today's report is built" block to Method page (`web/templates/method.html` + `web/app.py`), dynamically stating tier rules and continuous severity weights from `rules.yaml` and linking to `stage10/REPORT_PARAMETERS.md`.
- [x] **Phase 3 — Next-Day Forecast**:
  - Pre-registered in `stage10/prereg_forecast.md` BEFORE running models (committed in `006fdf6`).
  - Implemented `stage10/forecast/data.py` with zero lookahead, measuring sales order lead lag across 2025 (mean 6.12 days, median 6.00 days, 100% $\ge 3$ days advance notice; 100% of due orders known on books).
  - Implemented candidate models (a-d) and walk-forward expanding window evaluation in `stage10/forecast/models.py`. Model (d) achieved 18.99% relative WAPE improvement over Model (b) on Target 1, with 90.76% interval coverage. Order book model achieved 0.0 WAPE on Target 2.
  - Shortage risk rule evaluated (184/184 true negatives in 2025 H2 calm operations).
  - Deployed model trained on full 2025 dataset, serialized to `stage10/forecast/model.pkl` with SHA256 `27ee53a9cb5d94b02f99385de68e229eb0f3982d7e67f2420dfe5aef8bc48518` recorded in `prereg_forecast.md`.
  - Evaluated on 10 demo days via `stage10/forecast/evaluate_demo.py` without retraining.
- [x] **Phase 4 — Seasonality & Lag Checks**:
  - Implemented and executed `stage10/forecast/seasonality_and_lag.py` (results stored in `stage10/forecast/seasonality_lag_results.json`).
  - False-alarm check: 215 calm days in 2025 evaluated; 0.0% customer backlog false alarms, 1.86% stockout false alarms. Demo Day 4 and Day 9 control behaviors analyzed.
  - Seasonality stress test (+40% Q4 ramp, +25% Friday bump on isolated DataFrame copy): confirmed 90/92 Q4 days (97.8%) preserved causal integrity without phantom attributions.
  - Physical response lag analysis: supplier delay to safety breach median is 5.5 days (within 7-day window); stockout to customer backlog is 0 days (immediate same-day propagation).
- [ ] **Phase 5 — Product: Tomorrow Outlook Block**:
  - `outlook.enabled: true` in `stage9/config/rules.yaml`
  - Dynamic render in `web/templates/home.html` below numbers strip, unit tests in `stage10/test_outlook.py`
- [ ] **Phase 6 — Documents, Final Verification, & Final Commit**:
  - Write `stage10/FORECAST_REPORT.md`, update all docs, regenerate screenshots, clean `./verify_all.sh`, update `stage9/FROZEN.json`, commit `stage10 forecast final`

- [x] **Pre-execution Backup**: Created `backups/stage9_pre_last/`
- [x] **Frozen Hashes Verified**: Stage 7 (`acd199...`) and Stage 8 (`983a4e...`) SHA256 match perfectly
- [x] **Phase A — Mail Safety**:
  - `send_check` without `--live` forces dry-run unconditionally (`force_dry_run=True`), zero SMTP calls, returns `SUCCESS_DRY_RUN`
  - `--live` strictly requires explicit flag, allowlist match, `SAGE_SEND_ENABLED=true`, and non-placeholder credentials
  - Removed all occurrences of `--send-now`
  - Scheduled send idempotency checks `sent_log.jsonl` for existing `SUCCESS_LIVE` on same date/recipient
  - `run_sage.sh` resets send mode to dry_run on start, wraps with `caffeinate -i` on macOS, and prints next scheduled run times (19:45 prepare / 20:00 send Asia/Kolkata)
  - Added and passed `stage9/test_mail_safety.py` (4/4 tests passed; sent_log line count preserved)
- [x] **Phase B — Insights Equals Truth Layer**:
  - PO #17 (completed) days overdue fixed to 0, receipt breakdown formatted clearly
  - PO #18 shows 139 days overdue (was due 2025-08-14)
  - Unified dual-source order analysis: Postgres for history <= 2025-12-31, SQLite for 2026
  - Cancelled-at-opening orders (48 orders, 652 units) accounted for in denominator
  - Dynamic table columns and footnote explaining 0 late-but-delivered units
  - Tested on 2025-12-31 (78.3%), 2026-01-09 (75.2%) across all periods (3/3 unit tests passed)
- [x] **Phase C — Opening Position, One Source**:
  - Demo Baseline Notice updated verbatim on `home.html` and `insights.html`
  - Documented 8 vs 48 orders and 630 vs 652 units (47 vs 48 orders) in `KNOWN_ISSUES.md` (Issue 9)
  - Detailed SO #223 unfulfilled on 2025-12-31 (22 units ordered, 0 shipped)
  - Added `test_so_223_standing_backlog_reconciliation` in `stage9/test_reconcile.py` (all tests passed)
  - Stated database equivalence range in `KNOWN_ISSUES.md` (Issue 10: strictly equal <= 2025-12-20)
- [x] **Phase D — Feed, Scoring and Honesty**:
  - Timestamped `stage10/prereg_demo_feed_v3.md` before regenerating feed
  - Corrected PO #19 expected date to 2 Jan in generator (making it 1 day overdue on 3 Jan under end-of-day semantics)
  - Separated Day 6 ("at safety stock (47 kg remaining)") vs Day 7 ("Raw material stockout on Steel Rod 10mm (0 kg in stock)") headlines
  - Regenerated feed deterministically with identical SHA256 pack hashes (`556c710259...`)
  - Validated all 6 feed checks via `validate_feed.py`
  - Fixed summary generator in `web/one_page_data.py`: 6-7 lines, 90-120 words, strictly fact-driven, intact framing sentence
  - Verified Day 1, 3, 7, 9 summaries verbatim (113, 113, 107, 110 words)
  - Implemented strict deterministic scoring rules in `stage10/demo_feed/score.py`
  - Added and passed unit tests in `stage10/test_score.py` (5/5 passed)
  - Evaluated and documented 3 scoring runs (First run: 10 Critical; v2 rules: 8 Hits, 0 Partials, 2 Misses; v3 rules: 9 Hits, 0 Partials, 1 Miss)
  - Documented honest cause of Day 8 Miss in `DEMO.md`
  - Reset live demo environment cleanly to Day 0 (2025-12-31 baseline)
- [x] **Phase E — Security and Hygiene**:
  - Replaced all legacy default tokens (`sage_dev_token_*`, `sage_operator_token_*`) with cryptographically random independent 16-byte hex tokens in `.env`
  - Zero default tokens in code, tests, docs, or scripts; verified with zero-hit grep
  - Controller token is independent and NOT derived from viewer token
  - Added clean login and cookie authentication; `?token=` on first visit redirects to clean URL with HTTP-only cookie
  - Deleted obsolete screenshots (`case_*`, `controller_demo_cases.png`, `*2025-02-03*`, `*2025-01-15*`)
  - Regenerated all screenshots from 2026 demo feed into `analytics/screenshots/final/`: Day 1, Day 3, Day 7 (with analyze expander open), Day 9, Day 10, Insights 2025-12-31, Insights 2026-01-09, Controller dashboard, Sample PDF preview
  - Moved obsolete demo code (`stage9/generate_demo_2026.py`, `stage9/test_cases.py`) to `backups/obsolete_demo/`
  - Removed obsolete "Demo cases" API endpoints from controller
  - Git hygiene: added `backups/`, `live/`, `*.pid`, `analytics/insights_cache/` to `.gitignore`; untracked `backups/` and `live/` from git; verified `git ls-files` shows only `.env.example`
  - Fixed R5 audit in `audit_reconcile_r.py` and `gate_a_full.py`: parses 7 Stage 7 expert DAG edges, 3 active 2025 sourcing edges, and 10 incidents from `incidents.yaml` & `business_events` with zero "Supplier None" and zero "0 DAG edges"
- [x] **Phase F — Unified Verification (`verify_all.sh`)**:
  - Unified script with 13-step protocol
  - 150 automated verification checks passed, zero failures, exit 0
  - Servers bind strictly to `127.0.0.1` on ports 8000 and 8001
  - Playwright `smoke_ui.py` passed 9/9 flows with sub-second response times
  - Ten-day rehearsal scored 9 Hits, 0 Partials, 1 Miss
- [x] **Phase G — Presentation Documents & Guides**:
  - `DEMO.md` with Part 0 verbatim 2-minute opening statement, Day-by-day script, 3-run scoring table, and Part 5 Likely Mentor Q&A
  - `OWNER_CHECKLIST.md` clean single-page guide with terminal setup, exact URLs, token names, live-send command, and expected table
  - `stage10/PROJECT_SUMMARY.md` covers 9 stages, real test counts (150 passed checks), 10 known issues, exact verification commands
  - `stage10/KNOWN_ISSUES.md` covers Issues 1 through 10 in full detail
- [x] **Phase H — Self-Audit & Packaging**:
  - `REQUIREMENTS_TRACE.md` completed with verification evidence for every single numbered prompt requirement
  - `stage9/FROZEN.json` updated with SHA256 of all 79 Stage 9/10/web/controller files
  - Live environment reset to 2025-12-31 baseline in DRY-RUN mode with all 10 packs queued
  - Verified ports 8000 & 8001 free, 0 live emails sent in test runs
  - Added clean login and cookie authentication; `?token=` on first visit redirects to clean URL with HTTP-only cookie
  - Deleted obsolete screenshots (`case_*`, `controller_demo_cases.png`, `*2025-02-03*`, `*2025-01-15*`)
  - Regenerated all screenshots from 2026 demo feed into `analytics/screenshots/final/`: Day 1, Day 3, Day 7 (with analyze expander open), Day 9, Day 10, Insights 2025-12-31, Insights 2026-01-09, Controller dashboard, Sample PDF preview
  - Moved obsolete demo code (`stage9/generate_demo_2026.py`, `stage9/test_cases.py`) to `backups/obsolete_demo/`
  - Removed obsolete "Demo cases" API endpoints from controller
  - Git hygiene: added `backups/`, `live/`, `*.pid`, `analytics/insights_cache/` to `.gitignore`; untracked `backups/` and `live/` from git; verified `git ls-files` shows only `.env.example`
  - Fixed R5 audit in `audit_reconcile_r.py` and `gate_a_full.py`: parses 7 Stage 7 expert DAG edges, 3 active 2025 sourcing edges, and 10 incidents from `incidents.yaml` & `business_events` with zero "Supplier None" and zero "0 DAG edges"
- [x] **Phase F — Unified Verification (`verify_all.sh`)**:
  - Implemented complete 13-step automated protocol in `verify_all.sh` (clean exit 0 on 100% pass)
  - Verified frozen hashes: `stage7/FROZEN.json` sha256 (`acd199cea42b75d221f32b06736318024dbc53ec6cb4e8c06a8e25dd87f4c920`) and `stage8/FROZEN.json` sha256 (`983a4e1ffabb592d49548185750dcd01e713e9dae3f9b7baf3ae360c615dbb56`)
  - Verified all 55 frozen stage baseline files byte-identical to `baseline_hashes.json` (pycache excluded)
  - Truth layer dual-method cross check: 173 on-time orders (Method 1=173, Method 2=173, match=True)
  - Page-vs-truth verification (`test_insights_truth.py`): 3/3 passed across dates and periods
  - All forensic audits passed (`orders_audit.py`, `r5_audit.py`, `metrics_audit.py`, `gate_a_full.py`, `audit_reconcile_r.py`)
  - Zero forbidden literals and zero legacy default tokens outside backups verified via automated scan
  - Mail safety unit tests (`test_mail_safety.py`) & `send_check.py` dry-run passed
  - Multi-date reconciliation suite (`test_reconcile.py`): 5/5 passed across 4 dates + 12 monthly CSVs
  - Deterministic scoring unit tests (`test_score.py`): 5/5 passed
  - Stage 9 comprehensive test suite (`test_stage9_final.py`): 67/67 passed
  - Both servers verified bound strictly to 127.0.0.1 (ports 8000 & 8001; 0.0.0.0 absent)
  - Playwright Smoke UI suite (`smoke_ui.py`): 9/9 flows passed with sub-second response times
  - Ten-day demo feed rehearsal: All 10 days fed, scored 9 Hits, 0 Partials, 1 Miss under pre-registration v3
  - Final reset & safety verification: Zero live emails sent during tests (3 == 3), live DB restored to Day 0 (2025-12-31) in Dry-run mode, servers stopped, ports free
- [ ] **Phase G — Presentation Documents & Guides**
- [ ] **Phase H — Self-Audit & Packaging**

---

## Master Checklist

### Phase 0 — Safety, Stale Processes, Backups
- [x] Back up stage9/ web/ controller/ live/ demo_data/ reports/ stage10/ to backups/stage9_pre_final/ (30 MB)
- [x] Stop stale processes on 8000/8001 (verified ports free)
- [x] Make run_sage.sh / stop_sage.sh robust (bind 127.0.0.1, stop pids, health URL checks)
- [x] Controller starts in Dry-run

### Phase 1 — Truth Layer & Forensic Reconciliation
- [x] Write stage9/baseline_hashes.json (64 hashes matching frozen stages)
- [x] Print DB row counts (main Postgres source of truth vs live SQLite)
- [x] Explain 10 orders vs 221 orders discrepancy (SQLite post-opening position vs Postgres 2025 history)
- [x] Create stage10/audit/truth.py → truth.json with independent cross-check (Method 1: 173, Method 2: 173, match=True)
- [x] Rewrite audit scripts (orders_audit.py, r5_audit.py, metrics_audit.py, gate_a_full.py, audit_reconcile_r.py)
- [x] Verify known facts:
  - Backorder behavior: simulator does not ship late (0 late-but-delivered by construction)
  - Supplier selection bug: choose_supplier called without current_day in daily_simulation.py (S1 & S2 idle)
  - PO #18: EastCoast Components, Steel Rod 10mm, 407 units, placed 2025-08-05, expected 2025-08-14, 0 received, 139 days overdue at 2025-12-31
  - PO #17: Supplier 5, ordered 150u, first receipt 105u (70%) on 2025-08-07, balance 45u on 2025-08-09
  - Master names: Suppliers 1 Sri Materials, 2 Bharat Steel, 3 Global Polymers, 4 EastCoast Components, 5 Copper & Co. Products 201 Widget Model X, 202 Widget Model Y. Materials 101 Steel Rod 10mm, 102 Plastic Granules, 103 Copper Wire.

### Phase 2 — Propagate Truth Everywhere
- [x] Replace hand-typed figures in all pages/docs with truth.json values
- [x] Grep for stale/projected numbers (2348, 2367, 3000, 1981, forbidden literals) -> 0 occurrences outside tests/audits
- [x] Update web/insights_data.py & web/templates/insights.html (4 fulfillment buckets: 173 on-time, 0 late, 2 partial, 46 unshipped; 652 open units; 78.3%)
- [x] Update opening position notice on home.html and insights.html verbatim
- [x] Update method.html with 4-cohort benchmark table and verified customer names
- [x] Document simulator settlement limitation and post-hoc disclosures in KNOWN_ISSUES.md

### Phase 3 — Product Logic Verification (F1–F7)
- [x] F1 end-of-day operational semantics
- [x] F2 banner tiers (CRITICAL, NEEDS ATTENTION, WATCH, NORMAL)
- [x] F3 alerts as root causes (standing backlog decoupled from banner tier)
- [x] F4 cause chains in plain words
- [x] F5 model-check line
- [x] F6 data-driven summaries (90–120 words verified across days)
- [x] F7 cards structure (headline, cause sentence, evidence label, 3-step expander)

### Phase 4 — Ten-Day Feed & Deterministic Scoring
- [x] Deterministic generator & 10 pack hashes verified
- [x] score.py scoring against prereg_demo_feed_v2.md: 6 HITS, 4 PARTIALS, 0 MISSES (0 false alarms on control day)
- [x] Viewer polling and controller buttons verified functional

### Phase 5 — Security & Mail Dispatch
- [x] Timing-safe controller auth (`hmac.compare_digest`) and session cookies
- [x] SAGE_CONTROLLER_TOKEN distinct from SAGE_WEB_TOKEN
- [x] send_check command with safe dry-run (SUCCESS_DRY_RUN) and live flags
- [x] Daily scheduler (19:45 prep / 20:00 send Asia/Kolkata timezone)

### Phase 6 — Unified Verification (verify_all.sh)
- [x] Created executable `./verify_all.sh` covering frozen hashes, truth generation, forensic audits, scoring, forbidden literals, dry-run mail, and pytest suite
- [x] Verified `./verify_all.sh` runs cleanly to exit 0

### Phase 7 — Rehearsal Artifacts & Presentation Guides
- [x] 5 fresh screenshots captured via Playwright into artifact directory & `analytics/screenshots/final/`
- [x] Comprehensive presenter guide in `DEMO.md`
- [x] Owner's quick reference checklist in `OWNER_CHECKLIST.md`

### Phase 8 — Self-Audit & Packaging
- [x] Comprehensive requirements traceability matrix written in `REQUIREMENTS_TRACE.md`
- [x] Clean `./verify_all.sh` run (all 67 tests passed, 0 failed)
- [x] `stage9/FROZEN.json` hash registry updated
- [x] Committed repository state as `stage9 final`

---

## Verified Truth Figures (`stage10/audit/truth.json`)
- **Total customer orders requested $\le$ 2025-12-31:** 221
- **On-time complete:** 173 orders (1,981 units)
- **Shipped late:** 0 orders (0 units) — simulator settlement limitation
- **Partly shipped:** 2 orders (23 ordered, 19 shipped, 4 open units — SO #164 & SO #184)
- **Unshipped:** 46 orders (648 open units)
- **Total unfulfilled:** 48 orders (652 open units)
- **Total ordered:** 2,652 units; **Total shipped:** 2,000 units; **Total open:** 652 units
- **On-time delivery rate:** 78.3%
- **Orders due in Jan 2026:** 9 orders (109 units)
- **Total sales orders in database:** 230
- **Total purchase orders in 2025:** 18 (S1: 0, S2: 0, S3: 4, S4: 10, S5: 4)
- **PO #18:** Supplier 4 (EastCoast Components), 407 units Steel Rod 10mm, ordered 2025-08-05, expected 2025-08-14, 0 received, 139 days overdue at 2025-12-31 (stuck order)
- **PO #17:** Supplier 5 (Copper & Co), 150 units Copper Wire, ordered 2025-07-26, expected 2025-08-07, received 105 units (70%) on 2025-08-07, balance 45 units on 2025-08-09
