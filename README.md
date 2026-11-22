# SAGE — Enterprise Causal AI & Operational Intelligence Platform

[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/Framework-FastAPI%20%7C%20Uvicorn-green.svg)](https://fastapi.tiangolo.com/)
[![Causal ML](https://img.shields.io/badge/Causal%20ML-DoWhy%20%7C%20NetworkX-orange.svg)](https://github.com/py-why/dowhy)
[![Accuracy](https://img.shields.io/badge/Causal%20Attribution-95%25%20Accuracy-success.svg)](#benchmark-evaluation-results)
[![Tests](https://img.shields.io/badge/Test%20Suite-41%2F41%20Passing-brightgreen.svg)](#testing--verification)
[![License](https://img.shields.io/badge/License-Proprietary%20Academic-lightgrey.svg)](#)

> **Core Research Framing:**  
> *"SAGE performs automated root-cause attribution and grounded operational decision-intelligence over multi-echelon manufacturing supply chains using an expert-defined Structural Causal Model."*

---

## 📌 Executive Overview

In modern discrete manufacturing and logistics, traditional Business Intelligence (BI) dashboards can report *that* a customer delivery is delayed, but cannot explain *why* it occurred. Standard machine learning models conflate correlation with causation—treating intermediate symptoms (such as assembly downtime or buffer depletion) as root causes.

**SAGE (Supply-chain Attribution & Grounded Explanation)** solves this fundamental limitation. SAGE integrates an **offline 32-node, 40-edge Structural Causal Model (SCM)** with an **online, sub-second operational intelligence platform**. By traversing backward along directed causal paths from flagged delivery symptoms, SAGE pinpoints the initiating operational root cause (e.g., an upstream supplier's 60% partial delivery five days prior) and synthesizes a verified, zero-hallucination executive brief with actionable 09:00 AM operational priorities.

---

## 🏗️ System Architecture

SAGE is organized into a clean **two-tier enterprise architecture**:

```
┌────────────────────────────────────────────────────────────────────────┐
│                   TIER 1: OFFLINE CAUSAL PIPELINE                      │
│   (Data Generating Process, SCM Estimation, Benchmark Evaluation)      │
│                                                                        │
│   [ERP Transaction Generator] ────► [365-Day Baseline Panel Store]    │
│            (Stages 1 - 4)                          │                   │
│                                                    ▼                   │
│                                      [Expert Causal DAG & SCM]         │
│                                            (Stages 5 - 7)              │
│                                                    │                   │
│                                                    ▼                   │
│                                      [Fitted Model: 32 Nodes, 40 Edges]│
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Outputs SCM & Anomaly Distributions
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   TIER 2: ONLINE OPERATIONAL PLATFORM                  │
│     (Real-Time Ingestion, Causal Attribution & Executive Briefing)     │
│                                                                        │
│   [Daily ERP Feed Ingestion]                                           │
│            │                                                           │
│            ▼                                                           │
│   [Modified Z-Score Anomaly Detector] (M_i > 3.5 & P99 Cutoffs)        │
│            │                                                           │
│            ▼                                                           │
│   [Backward Path Attribution Engine] ──► Root Cause Identification     │
│            │                                                           │
│            ▼                                                           │
│   [Grounded Narration Engine] ─────────► Zero-Hallucination Assertion  │
│            │                                                           │
│            ├──► Executive Web Dashboard (Port 8000: Viewer)            │
│            ├──► Operator Control Panel  (Port 8001: Controller)        │
│            └──► Automated A4 Executive Briefing (ReportLab / PDF)      │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 📁 Repository Directory Map

The codebase is organized into modular engineering tiers:

```
sage-starter/
├── web/                     # Executive Viewer Application (FastAPI + Jinja2)
│   ├── app.py               # Viewer routes, KPI endpoints, and session auth
│   ├── auth.py              # Salted scrypt key derivation, sessions, and CSRF
│   ├── one_page_data.py     # Grounded narration engine & daily brief compiler
│   └── templates/           # Server-side rendered executive dashboards
├── controller/              # Operator Control Console (FastAPI + Jinja2)
│   ├── app.py               # Administrative actions, test-runs, and email controls
│   └── templates/           # Dark-themed operator control interfaces
├── stage7/                  # Expert Structural Causal Model (SCM)
│   ├── build_causal_model.py# 32-node, 40-edge DAG construction & DoWhy fitting
│   └── fitted_causal_model.pkl # Serialized causal model parameters
├── stage9/                  # Daily Operational Engine & Dispatch
│   ├── snapshot.py          # Daily panel computation, status tier assignment
│   ├── smtp_sender.py       # Production email dispatch with idempotency guards
│   ├── state/               # SQLite operational store, users, and audit logs
│   └── config/rules.yaml    # Pre-registered business rules & safety thresholds
├── stage10/                 # Continuous Evaluation & Visualization
│   ├── demo_feed/           # 10-day disruption feed (2026-01-01 to 2026-01-10)
│   ├── figures/             # Graphviz/NetworkX causal DAG figure generators
│   └── demo_feed_results.md # Benchmark evaluation reports
├── live/                    # ACID-compliant SQLite operational database (sage_live.db)
├── analytics/               # 365-day baseline panel (daily_panel_baseline.parquet)
├── reports/                 # Compiled A4 PDF and HTML daily briefs
├── run_sage.sh              # One-click startup script with health checks
└── stop_sage.sh             # Graceful shutdown script
```

---

## 📊 Benchmark Evaluation Results

SAGE was evaluated across a continuous **10-day operational disruption feed** (01–10 Jan 2026) featuring complex real-world manufacturing shocks:

| Day | Date | Daily Rows | Status Tier | Top Operational Headline | Attributed Root Cause | Match Score |
| :---: | :---: | :---: | :---: | :--- | :--- | :---: |
| **D-01** | 2026-01-01 | 37 | **WATCH** | Elevated demand intake (Model X surge: 15u) | Demand surge absorbed by finished goods buffer | **PARTIAL** |
| **D-02** | 2026-01-02 | 39 | **WATCH** | Elevated demand intake (Model X surge: 36u) | Finished goods inventory buffers demand spike | **HIT** |
| **D-03** | 2026-01-03 | 36 | **NEEDS ATTENTION** | Overdue delivery from EastCoast Components (PO #19) | Inbound PO #19 transit delay (1d late) | **HIT** |
| **D-04** | 2026-01-04 | 41 | **NEEDS ATTENTION** | Overdue PO #19; partial plastic receipt (60%) | Dual supplier delay: PO #19 late + PO #20 partial | **HIT** |
| **D-05** | 2026-01-05 | 38 | **NEEDS ATTENTION** | Inbound PO #19 overdue (3d late) | Raw material safety cover deteriorating | **HIT** |
| **D-06** | 2026-01-06 | 45 | **CRITICAL** | Steel at safety stock (50 kg) with PO overdue | Critical buffer breach triggering assembly risk | **HIT** |
| **D-07** | 2026-01-07 | 35 | **CRITICAL** | Raw material stockout on Steel Rod 10mm (0 kg) | Total steel stockout halts assembly lines | **HIT** |
| **D-08** | 2026-01-08 | 58 | **NEEDS ATTENTION** | Inbound recovery & production restart | Delayed PO arrives; backlog cleared via FIFO dispatch | **HIT** |
| **D-09** | 2026-01-09 | 42 | **NORMAL** | Nominal operations; planned schedules achieved | All POs on time; 0 overdue customer backorders | **HIT** |
| **D-10** | 2026-01-10 | 44 | **NEEDS ATTENTION** | Line 2 assembly capacity shortfall (-20%) | Internal assembly deficit draws down finished buffer | **HIT** |

* **Strict Causal Hits:** 9 / 10 (90%)
* **Partial Matches:** 1 / 10 (10%)
* **False Attributions (Misses):** 0 / 10 (0%)
* **Composite Accuracy Score:** **95.0%**

---

## 🔒 Security & Verification Highlights

1. **Grounded, Zero-Hallucination Narration:** Text statements in daily executive briefings are deterministically bound to verified database rows. Every PO ID, supplier name, delayed quantity, and stock level is validated against transactional records.
2. **Zero-Leakage Assurance:** Automated AST scanners verify that confidential simulation parameters and answer keys (`INC_*` tags) never leak into customer-facing HTML, PDFs, or logs.
3. **Enterprise Authentication:** Operator console uses salted `scrypt` password hashing (16,384 rounds) and timing-safe double-submit CSRF token validation.
4. **Transport Safety:** Test suites operate on a mock transport fixture (`SAGE_MAIL_TRANSPORT=mock`), guaranteeing that automated testing never triggers network SMTP calls.

---

## 🚀 Quickstart & Demonstration

### 1. Requirements
* macOS or Linux
* Python 3.12+
* Standard scientific and web dependencies (`pip install -r requirements.txt`)

### 2. Launch the Platform
```bash
# Start both Executive Viewer and Operator Controller with automatic health checks
bash run_sage.sh
```

### 3. Web Interfaces & Credentials
* **Executive Viewer:** [http://127.0.0.1:8000/](http://127.0.0.1:8000/)  
  *Explore daily operational briefs, interactive causal DAGs, and inventory KPI trends.*
* **Operator Controller:** [http://127.0.0.1:8001/ctrl/](http://127.0.0.1:8001/ctrl/)  
  *Simulate test runs, check connection diagnostics, and manage automated dispatch.*
* **Default Credentials:**
  * **Admin:** `admin` / `SageAdmin2026!`
  * **Operator:** `operator` / `SageAdmin2026!`

### 4. Stopping the Services
```bash
./stop_sage.sh
```

---

## 🧪 Testing & Verification

Execute the unified test harness covering data integrity, email safety, and causal scoring:

```bash
SAGE_MAIL_TRANSPORT=mock ./verify_all.sh
```
*All 41 test suites validated passing with 100% compliance.*

---

## 📜 Scientific Framing & Citations
*Pearl, J. (2009). Causality: Models, Reasoning, and Inference. Cambridge University Press.*  
*Peters, J., Janzing, D., & Schölkopf, B. (2017). Elements of Causal Inference. MIT Press.*  
*Sharma, A., & Kiciman, E. (2020). DoWhy: An End-to-End Library for Causal Inference. arXiv:2011.04216.*
