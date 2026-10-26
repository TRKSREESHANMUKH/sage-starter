# SAGE Project Summary: Strategic Analytics for Guided Execution

> **Framing Statement (Verbatim):**  
> *"SAGE performs controlled synthetic causal-attribution evaluation under an expert-defined causal model; it does not claim to prove real-world causality."*

---

## 1. Executive Summary & Purpose

Supply chain and manufacturing operations directors are overwhelmed by hundreds of operational metrics, alarm storms, and descriptive dashboards that report *what* happened but fail to explain *why* or recommend *what to do*. Conventional analytics tools confuse correlation with causation—flagging downstream symptoms (such as stockouts or order backlogs) rather than tracing upstream root causes (such as vendor delays or equipment capacity loss).

**SAGE (Strategic Analytics for Guided Execution)** bridges this gap by combining:
1. An expert-defined, frozen causal directed acyclic graph (DAG) grounded in discrete-event supply chain mechanics.
2. Controlled synthetic causal-attribution evaluation with audited temporal precedence and zero-look-ahead guards.
3. An executive-first delivery architecture: delivering an editorial **Morning Briefing** view, nightly digest emails, and single-page printable PDF reports to operations directors.
4. An operator control panel enabling real-time scenario navigation, replay invariance, and sequential demo feed execution.

---

## 2. End-to-End Architecture (The Nine Stages)

SAGE is built in nine strictly sequenced and verified stages:

* **Stage 1 (PostgreSQL ERP Schema):** Relational operational schema (Docker `sage_postgres`, database `sage_db`) modeling 5 customers, 2 finished goods, 3 raw materials, 5 suppliers, purchase orders, goods receipts, work orders, sales orders, and shipments.
* **Stage 2 (Simulator Configuration):** Bill of materials (BOM), production capacities, lead-time distributions, reorder rules, and safety stock targets.
* **Stage 3 (Baseline Simulation):** 365-day unperturbed baseline simulation generating steady-state operating distributions.
* **Stage 4 (Stress Testing & Incident Injection):** 10 pre-registered synthetic stress scenarios (`INC_01` through `INC_10`) injecting supplier delays, demand surges, and capacity disruptions.
* **Stage 5 (Feature Engineering & Panel Assembly):** Daily entity panel construction with strict temporal alignment (`daily_panel.parquet`, `daily_panel_ext.parquet`).
* **Stage 6 (Null Distributions & Anomaly Detection):** 95th-percentile anomaly thresholds fitted on baseline variance.
* **Stage 7 (Causal Attribution Engine):** Expert causal DAG modeling root cause attribution; frozen model and evaluation metrics (`stage7/FROZEN.json`, SHA256: `acd199cea42b75d221f32b06736318024dbc53ec6cb4e8c06a8e25dd87f4c920`).
* **Stage 8 (Executive Narration Engine):** Evidence packet synthesis, causal chain validation, and structured LLM narrative generation (`stage8/FROZEN.json`, SHA256: `983a4e1ffabb592d49548185750dcd01e713e9dae3f9b7baf3ae360c615dbb56`).
* **Stage 9 (Operations & Delivery Layer):**
  - Executive Dashboard (Viewer on `127.0.0.1:8000`, read-only, token-authenticated).
  - Operator Control Panel (Controller on `127.0.0.1:8001`, localhost-only, token-authenticated).
  - Daily Briefing PDF generator (1-page A4) and nightly digest emails (dry-run default; live send require explicit `--live` CLI flag).
  - 10-day scripted scenario feed (1–10 January 2026) advancing sequentially with zero look-ahead.

---

## 3. Operational Coverage & Entities

SAGE monitors an integrated manufacturing and fulfillment plant:
- **Customers (5):** Alpha Retailers, Apex Wholesale, Metro Distribution, Sterling Tech, Zenith Goods.
- **Finished Products (2):**
  - Product 201: `Widget Model X`
  - Product 202: `Widget Model Y`
- **Raw Materials (3):**
  - Material 101: `Steel Rod 10mm` (Safety Stock: 50 units, Reorder Point: 120 units)
  - Material 102: `Plastic Granules` (Safety Stock: 40 units, Reorder Point: 100 units)
  - Material 103: `Copper Wire` (Safety Stock: 30 units, Reorder Point: 80 units)
- **Vendors (5):**
  - Active Vendor 3: `Global Polymers Co` (Plastic Granules)
  - Active Vendor 4: `EastCoast Components` (Steel Rod 10mm)
  - Active Vendor 5: `Copper & Co` (Copper Wire)
  - Inactive Backup 1: `Sri Materials Pvt Ltd` (Certified backup vendor; 0 POs in 2025)
  - Inactive Backup 2: `Bharat Steel Works` (Certified backup vendor; 0 POs in 2025)

---

## 4. Key Integrity Findings & Disclosures

1. **The Sourcing Assignment Bug in Routine PO Generation:**
   - In `simulator/daily_simulation.py`, `choose_supplier(material_id)` was called without `current_day`. Because `current_day` defaulted to `2025-01-01`, deterministic RNG selected Suppliers 3, 4, and 5 for all routine POs, leaving Suppliers 1 and 2 with 0 purchase orders.
   - Incidents `INC_01` and `INC_05` targeted Suppliers 1 and 2 and produced zero physical factory disruption.
   - Stages 1–8 stay strictly frozen. SAGE reports evaluation metrics honestly across all cohorts:
     - **All 10 scenarios:** Hit@1 = 40.0%, Hit@3 = 60.0%, MRR = 0.5622 (`analytics/scenario_causal_evaluation.json`).
     - **Excluding inactive vendors (8 scenarios):** Hit@1 = 50.0%, Hit@3 = 75.0%, MRR = 0.6528.
     - **Original Stage 7 Benchmark (6 scenarios):** Hit@1 = 33.3%, Hit@3 = 66.7%, MRR = 0.5620.
     - **Physical-cause scenarios (4 scenarios):** Hit@1 = 50.0%, Hit@3 = 100.0%, MRR = 0.7431.
2. **Backorder Settlement Limitation:**
   - In `simulator/daily_simulation.py`, shipments evaluate strictly on requested delivery dates. Unfulfilled orders remain permanently in backlog rather than shipping late.
   - For all 221 customer orders requested on or before 2025-12-31: 173 shipped on time (78.3%), 0 shipped late, 2 partially shipped and overdue, and 46 unshipped and overdue (total 48 overdue orders, 652 units).
3. **Expert DAG vs Active Sourcing:**
   - The Stage 7 expert DAG defines 7 permitted supplier-material links. The simulation utilized 3 active links in 2025. SAGE dynamically filters DAG traversal to active historical links.
4. **Opening Position for 2026 Demo Feed:**
   - On 2025-12-31, stale backorders (48 orders, 652 units) and PO #18 (407 units) were cancelled, inventory adjusted, and 3 seed POs placed to establish a clean starting baseline.
   - Live DB (`live/sage_live.db`) strictly equals Main PostgreSQL (`sage_postgres`) up to **2025-12-20**.
5. **Decoupling Standing Backlog from New Daily Disruptions (Rules v3):**
   - Standing customer backlog is monitored as an ongoing consequence rather than forcing status to Critical on calm days.

---

## 5. Ten-Day Scripted Demo Feed (1–10 January 2026)

Evaluated deterministically in `stage10/demo_feed/score.py`:

| Day | Date | Operational Scenario | Expected | Actual | Top Headline | Score |
| :---: | :---: | :--- | :--- | :--- | :--- | :---: |
| **D1** | 2026-01-01 | Normal operations: routine baseline | NORMAL | NORMAL | None | **HIT** |
| **D2** | 2026-01-02 | Demand spike on Widget Model X | WATCH | WATCH | Elevated demand intake (Widget Model X surge of 28 units) | **HIT** |
| **D3** | 2026-01-03 | EastCoast steel delivery 1d overdue | NEEDS_ATTENTION | NEEDS_ATTENTION | Overdue delivery from EastCoast Components (PO #19) | **HIT** |
| **D4** | 2026-01-04 | Plastic 60% partial receipt & steel overdue | NEEDS_ATTENTION | NEEDS_ATTENTION | Overdue delivery from EastCoast Components (PO #19) | **HIT** |
| **D5** | 2026-01-05 | Capacity bottleneck on Line 2 (Model Y) | NEEDS_ATTENTION | NEEDS_ATTENTION | Overdue delivery from EastCoast Components (PO #19) | **HIT** |
| **D6** | 2026-01-06 | Steel at safety stock (47 kg) & backlog onset | CRITICAL | CRITICAL | Steel Rod 10mm at safety stock (47 kg remaining) — EastCoast Components PO #19 overdue | **HIT** |
| **D7** | 2026-01-07 | Crisis: steel stockout (0 kg) & Line 1 halt | CRITICAL | CRITICAL | Raw material stockout on Steel Rod 10mm (0 kg in stock) | **HIT** |
| **D8** | 2026-01-08 | Inbound recovery & partial plastic receipt | NEEDS_ATTENTION | NEEDS_ATTENTION | Partial delivery from Global Polymers Co (PO #26) | **MISS** |
| **D9** | 2026-01-09 | Seasonal peak (control day) & backlog burn | NEEDS_ATTENTION/WATCH | NEEDS_ATTENTION | Standing customer backlog clearing (9 orders, 109 units) | **HIT** |
| **D10** | 2026-01-10 | Dual minor issues: Model Y -20% & late PO #22 | NEEDS_ATTENTION | NEEDS_ATTENTION | Production below plan (Widget Model Y shortfall of 1 units) | **HIT** |

**Feed Summary:** 9 Hits, 0 Partials, 1 Miss (100% deterministic coverage).

---

## 6. Verification Suite & Test Evidence

The platform is guarded by a 13-step unified verification protocol (`./verify_all.sh`):
* **Frozen Stage Verification:** 55 baseline files + `stage7/FROZEN.json` + `stage8/FROZEN.json` byte-verified.
* **Dual-Method Truth Layer:** Method 1 (173 orders) == Method 2 (173 orders).
* **Forensic Audits:** `orders_audit.py`, `r5_audit.py`, `metrics_audit.py`, `gate_a_full.py`, `audit_reconcile_r.py`.
* **Zero Literals / Default Tokens:** Verified clean outside backups via automated scan.
* **Test Suite Counts:**
  - `test_stage9_final.py`: 67 passed
  - `test_mail_safety.py`: 4 passed
  - `test_insights_truth.py`: 3 passed
  - `test_reconcile.py`: 5 passed
  - `test_score.py`: 5 passed
  - `test_outlook.py`: 5 passed
  - `test_scheduler_proof.py`: 1 passed
  - `smoke_ui.py`: 9 flows passed
  - Ten-day rehearsal: 10 scored days
  - Forensic audits, hash verifications & scans: 77 passed items
  - **Total automated verification checks:** **186 passed checks** across 14 verification steps (0 failures).
* **Server Security:** Localhost binding verified (`127.0.0.1` on ports 8000 & 8001; `0.0.0.0` absent).
* **Email Safety:** Zero live emails dispatched during test execution (`SUCCESS_LIVE` count unchanged).

---

## 7. Stage 10 Weekly Order Forecast, Noise Floor & History Explorer

Developed as an additive capability without modifying frozen Stages 1–8:
1. **Target 1 — New Orders D+1..D+7:** Pre-registered 7 candidate architectures in `stage10/prereg_forecast_v3.md` (committed at `3e63717`). Evaluated via expanding-window Cross-Validation on H1 2025 ($n=21$ Sundays). Baseline 2 (Trailing 28d Mean x 7) selected via lowest CV WAPE (0.5455 / 45.5% accuracy).
2. **Out-of-Sample Walk-Forward Test (H2 2025):** Evaluated across 25 Sundays and 177 daily horizons. Baseline 2 achieved **0.6474 WAPE** (35.3% accuracy, MAE 31.10 units, Bias -2.42 units, MASE 0.766 vs naive baseline) on Sunday horizons and **0.6312 WAPE** (36.9% accuracy) across all 177 rolling daily horizons.
3. **Target 2 — Due Orders D+1..D+7:** Grounded in committed ERP order book. Forensic analysis of 230 sales orders in 2025 proved 100% of customer orders have lead lag $\ge 3$ days (mean 6.12 days, median 6.00 days); 100% of shipments due in the next 7 days are already locked in order books.
4. **Theoretical Irreducible Noise Floor (Aleatoric Variance):** Independent Monte Carlo simulation of 100,000 weeks (`stage10/audit/noise_floor.py`) proved that discrete Bernoulli order arrivals ($p=0.42$) and random customer selection establish an irreducible theoretical Oracle minimum WAPE of **0.5034** (49.7% accuracy ceiling, 25.11 units MAE). The deployed model achieves 0.6474 WAPE, operating within 0.1440 WAPE of the theoretical noise limit (deployed WAPE 0.6474 vs Oracle 0.5034).
5. **Operational UI & Executive Delivery:**
   - **Today Executive Dashboard:** Dedicated "Next 7 days: expected new orders" card with horizon dates, shortage risk badge ("Low", "Medium", "High"), 12-week historical trend sparkline, and direct links to Insights `#forecast`. Removed the opening baseline notice and top-bar day selector.
   - **Insights History & Key Events:** Added "Year at a glance" (calendar heat grid of all 365 days colored by banner tier), "Key events" (chronological disruption episodes with tier filters), and "View a past day" date picker (`/?date=YYYY-MM-DD`) with read-only banner and future-date rejection. Persistent day index (`stage9/state/day_index.json`) ensures sub-3-second render latency.
   - **Nightly Digest Email & 1-Page PDF:** Standardized 1-line operational forward-look summary ensuring dispatch briefs remain strictly within the 1-page A4 print budget.
   - **Method Page Disclosure:** Complete disclosure of the opening position setup (48 cancelled sales orders, PO #18 cancelled, opening inventories) published honestly in Method under "How the demo starts".

