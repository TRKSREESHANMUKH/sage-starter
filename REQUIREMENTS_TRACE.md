# SAGE Stage 9 Final — Comprehensive Requirements Traceability Matrix

> **Scientific Framing Statement:**  
> *"SAGE performs controlled synthetic causal-attribution evaluation under an expert-defined causal model; it does not claim to prove real-world causality."*

---

## 1. Global Architectural & Security Rules

| Rule ID | Requirement Specification | Implementation Artifact | Verification Proof / Test ID | Status |
| :--- | :--- | :--- | :--- | :---: |
| **GR-01** | Stages 1–8 strictly frozen (hashes unchanged) | `stage7/FROZEN.json`, `stage8/FROZEN.json`, `stage9/baseline_hashes.json` | Hash check in `verify_all.sh` (`test_g1`) | **PASS** |
| **GR-02** | Main PostgreSQL database is read-only | `web/insights_data.py` (`SET default_transaction_read_only = on`) | `test_g25`, `truth.py` read-only connection | **PASS** |
| **GR-03** | Mandatory framing statement verbatim on every UI page, email, PDF | `stage9/status.py`, `web/templates/*.html`, `stage9/render_email.py` | `test_g15` (HTML & text bodies, PDF renderer) | **PASS** |
| **GR-04** | Zero hand-typed / projected figures; full forensic traceability | `stage10/audit/truth.py`, `truth.json` | `orders_audit.py`, `gate_a_full.py`, `truth.json` cross-check | **PASS** |
| **GR-05** | Plain English for plant managers; no internal stack traces or SQL | Templates, `stage9/narrate.py`, `stage9/priorities.py` | `test_b3_1`, AST inspection | **PASS** |
| **GR-06** | Zero forbidden literals outside tests/audits | Codebase clean | Grep check in `verify_all.sh` (0 hits) | **PASS** |

---

## 2. Phase 0: Server Lifecycle & Process Management

| Phase ID | Requirement Specification | Implementation Artifact | Verification Proof / Test ID | Status |
| :--- | :--- | :--- | :--- | :---: |
| **P0-1** | Stop stale server processes on 8000/8001 | `stop_sage.sh`, `run_sage.sh` | Port check via `lsof -nP -i :8000 -i :8001` | **PASS** |
| **P0-2** | Backup stage9/, web/, controller/, live/, demo_data/, reports/, stage10/ | `backups/stage9_pre_final/` | 30 MB directory backed up | **PASS** |
| **P0-3** | HTTP 200 `/health` check before declaring server start | `web/app.py#L48`, `controller/app.py#L75`, `run_sage.sh` | `curl -s http://127.0.0.1:8000/health` returns 200 | **PASS** |
| **P0-4** | Controller boots in safe DRY-RUN send mode | `controller/app.py#L125` | `test_g6`, startup log verification | **PASS** |

---

## 3. Phase 1: Truth Layer & Forensic Reconciliation

| Phase ID | Requirement Specification | Implementation Artifact | Verification Proof / Test ID | Status |
| :--- | :--- | :--- | :--- | :---: |
| **P1-1** | Baseline hashes for all stage1..8 files | `stage9/baseline_hashes.json` (64 files) | `verify_all.sh` baseline hash check | **PASS** |
| **P1-2** | Explain 10 vs 221 orders discrepancy | `HANDOFF.md`, `truth.py` | PostgreSQL 2025 history (221 req <= 2025-12-31) vs SQLite demo opening position (10 orders) | **PASS** |
| **P1-3** | Generate ground truth with dual independent cross-check | `stage10/audit/truth.py` -> `truth.json` | Method 1 (173 on-time) == Method 2 (173 on-time), match=True | **PASS** |
| **P1-4** | Forensic audits rewritten to read truth dynamically | `orders_audit.py`, `r5_audit.py`, `metrics_audit.py`, `gate_a_full.py`, `audit_reconcile_r.py` | All 5 scripts execute cleanly with zero hardcoded values | **PASS** |
| **P1-5** | Late-but-delivered order count verified as 0 | `orders_audit.py`, `KNOWN_ISSUES.md#Issue-7` | Simulator settlement limitation proven by construction | **PASS** |
| **P1-6** | PO #18 (EastCoast Components, Steel) 139d overdue | `truth.json#po_18`, `KNOWN_ISSUES.md#Issue-5` | Due 2025-08-14, 0 received through 2025-12-31 | **PASS** |
| **P1-7** | PO #17 (Copper & Co, Copper Wire) 70% first receipt | `truth.json#po_17` | 105u received 2025-08-07, 45u balance 2025-08-09 | **PASS** |

---

## 4. Phase 2: Truth Propagation Across Product UI & Documents

| Phase ID | Requirement Specification | Implementation Artifact | Verification Proof / Test ID | Status |
| :--- | :--- | :--- | :--- | :---: |
| **P2-1** | Four fulfillment buckets in Insights tab | `web/insights_data.py`, `web/templates/insights.html` | 173 on-time (1981u), 0 late (0u), 2 partial (19 shipped, 4 open), 46 unshipped (648 open) | **PASS** |
| **P2-2** | Opening position notice updated verbatim | `web/templates/home.html#L437`, `web/templates/insights.html#L387` | Clean manager-facing phrasing, technical jargon removed | **PASS** |
| **P2-3** | Multi-cohort benchmark table on Method page | `web/templates/method.html#L25-L65` | Displays All 10 (40%/60%/0.5622), Excl Sourcing Bug (50%/75%/0.6528), Orig 6 (33%/67%/0.5620), Physical 4 (50%/100%/0.7431) | **PASS** |
| **P2-4** | Verified customer entity names | `web/templates/method.html#L143` | Real names: Nova Retailers, Metro Distributors, Coastal Traders, Prime Retail Group, Sunrise Wholesalers | **PASS** |
| **P2-5** | Idle backup vendors collapsed into one line | `web/insights_data.py`, `web/templates/insights.html` | *"No orders placed in this period: Sri Materials Pvt Ltd, Bharat Steel Works (backup vendors)"* | **PASS** |

---

## 5. Phase 3 & 4: Product Logic, Ten-Day Demo Feed & Scoring

| Phase ID | Requirement Specification | Implementation Artifact | Verification Proof / Test ID | Status |
| :--- | :--- | :--- | :--- | :---: |
| **P3-1** | End-of-day operational semantics (F1) | `stage9/clock.py`, `stage9/current_day.py` | Data observed up to current_day | **PASS** |
| **P3-2** | Operational banner tiers (F2) | `stage9/config/rules.yaml`, `stage9/status.py` | CRITICAL, NEEDS ATTENTION, WATCH, NORMAL | **PASS** |
| **P3-3** | Root-cause alerts with cause chains (F3, F4) | `stage9/priorities.py`, `stage9/trace.py` | Physical root drivers identified; 3-step expander | **PASS** |
| **P3-4** | Data-driven summaries 90–120 words (F6) | `web/one_page_data.py#L756-L822` | Verified: Day 1 (113w), Day 3 (113w), Day 7 (110w), Day 9 (110w) | **PASS** |
| **P3-5** | Deterministic 10-day generator & pack hashes | `stage10/demo_feed/generate_demo_feed.py` | 10 packs in `demo_data/packs` (`test_g10`) | **PASS** |
| **P3-6** | Deterministic scoring engine (score.py) | `stage10/demo_feed/score.py` | 6 Hits, 4 Partials, 0 Misses against `prereg_demo_feed_v2.md` | **PASS** |

---

## 6. Phase 5: Security & Mail Dispatch

| Phase ID | Requirement Specification | Implementation Artifact | Verification Proof / Test ID | Status |
| :--- | :--- | :--- | :--- | :---: |
| **P5-1** | Timing-safe controller auth & session cookies | `controller/app.py` | `test_g18` to `test_g21`, `hmac.compare_digest` | **PASS** |
| **P5-2** | Distinct controller vs viewer tokens | `.env`, `controller/app.py` | `test_g27` (controller token derived and distinct) | **PASS** |
| **P5-3** | Safe send check in dry-run mode | `stage9/send_check.py` | `test_g6`, `./venv/bin/python -m stage9.send_check` (SUCCESS_DRY_RUN) | **PASS** |
| **P5-4** | Daily scheduler (19:45 prep / 20:00 send IST) | `stage9/scheduler.py`, `stage9/config/schedule.yaml` | `test_g8` (Asia/Kolkata timezone verification) | **PASS** |

---

## 7. Phase 6, 7 & 8: Verification, Artifacts & Final Packaging

| Phase ID | Requirement Specification | Implementation Artifact | Verification Proof / Test ID | Status |
| :--- | :--- | :--- | :--- | :---: |
| **P6-1** | One-command verification script | `verify_all.sh` | `./verify_all.sh` executes all checks to exit 0 | **PASS** |
| **P7-1** | Fresh UI rehearsal screenshots | `analytics/screenshots/final/`, artifacts | 5 full-resolution PNG screenshots captured | **PASS** |
| **P7-2** | Presenter guide & Owner checklist | `DEMO.md`, `OWNER_CHECKLIST.md` | Clear, actionable rehearsal and presentation instructions | **PASS** |
| **P8-1** | Frozen hashes registry updated | `stage9/FROZEN.json` | Hash records updated and verified | **PASS** |
| **P8-2** | Clean git commit | Repository state | Committed as `stage9 final` | **READY** |
