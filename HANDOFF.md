# SAGE Stage 9 Final — HANDOFF

## Status: IN PROGRESS — Executing "THE LAST PROMPT" (Phases A through H)

Stages 1–8 strictly frozen. Main PostgreSQL database protected read-only (`SET default_transaction_read_only = on`). All figures traced to truth layer. No live email sent.

---

## The Last Prompt — Execution Progress
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
- [ ] **Phase E — Security and Hygiene**
- [ ] **Phase E — Security and Hygiene**
- [ ] **Phase F — Unified Verification (`verify_all.sh`)**
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
