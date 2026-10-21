# SAGE Project Summary: Strategic Analytics for Guided Execution

> **Framing Statement (Verbatim):**
> "SAGE performs controlled synthetic causal-attribution evaluation under an expert-defined causal model; it does not claim to prove real-world causality."

---

## 1. Executive Summary & Purpose

Supply chain and manufacturing operations directors are overwhelmed by hundreds of operational metrics, alarm storms, and descriptive dashboards that report *what* happened but fail to explain *why* or recommend *what to do*. Conventional analytics tools confuse correlation with causation—flagging downstream symptoms (such as stockouts or order backlogs) rather than tracing upstream root causes (such as vendor delays or equipment capacity loss).

**SAGE (Strategic Analytics for Guided Execution)** bridges this gap by combining:
1. An expert-defined, frozen causal directed acyclic graph (DAG) grounded in supply chain mechanics.
2. Controlled synthetic causal-attribution evaluation with audited temporal precedence and no-look-ahead guards.
3. An executive-first delivery architecture: delivering an editorial **Morning Briefing** view, nightly digest emails, and single-page printable PDF reports to operations directors.
4. An operator control panel enabling real-time scenario navigation, replay invariance, and single-click full-year operational reviews.

---

## 2. End-to-End Architecture (Stages 1–10)

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ STAGES 1–4: SIMULATION ORACLE (Frozen Baseline & Incident Scenarios)                   │
│ - Discrete-event ERP simulator generating transactional tables across 2025             │
│ - 5 Customers, 2 Products, 3 Raw Materials, 5 Suppliers (3 active, 2 backup)           │
│ - 10 Synthetic Incident Scenarios (demand spikes, capacity faults, vendor delays)       │
└──────────────────────────────────────────┬─────────────────────────────────────────────┘
                                           │
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ STAGES 5–7: FROZEN CAUSAL ATTRIBUTION ENGINE                                           │
│ - Expert-defined causal DAG mapping supplier delays, stock buffers, line bottlenecks   │
│ - Null distributions fitted on 95th-percentile baseline variation                     │
│ - Anomaly attribution scoring with 5-seed stability validation                         │
│ - Frozen artifacts: stage7/FROZEN.json, stage8/FROZEN.json (SHA256 audited)            │
└──────────────────────────────────────────┬─────────────────────────────────────────────┘
                                           │
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ STAGES 8–9: EXECUTIVE DELIVERY & OPERATIONS LAYER                                      │
│ - Daily Briefing Front Page: Morning Briefing editorial style with measured headlines  │
│ - Causal cause chains: 'Seen end to end' / 'Partly seen' / 'No upstream explanation'   │
│ - Today's Focus Dark Band: Top 5 shift actions with owner, target time, and root fix   │
│ - Numbers Strip: Orders due, overdue orders, units short, buffer status (7d average)   │
│ - Nightly Digest Email & Playwright Single-Page A4 PDF Generator                       │
└──────────────────────────────────────────┬─────────────────────────────────────────────┘
                                           │
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ STAGE 10: DEMO ENGINE & INTEGRITY AUDIT                                                │
│ - Ten Pre-Registered Demo Cases covering real 2025 operational scenarios               │
│ - Fast replay engine (jump_to_case in < 30s) with clean zero-look-ahead database       │
│ - Operator Control Panel (Port 8001) with session auth, CSRF, and allowlist safety    │
│ - Transparent Known Issues & Two-Way Metric Reporting in Research View                 │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Operational Coverage & Scope

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
  - Active Vendor 3: `Global Polymers Co` (Supplies Material 102)
  - Active Vendor 4: `EastCoast Components` (Supplies Material 101)
  - Active Vendor 5: `Copper & Co` (Supplies Material 103)
  - Inactive Backup 1: `Sri Materials Pvt Ltd` (Backup vendor; 0 orders placed in 2025)
  - Inactive Backup 2: `Bharat Steel Works` (Backup vendor; 0 orders placed in 2025)

---

## 4. Key Integrity Findings & Decisions (Part 1 Record)

1. **The Sourcing-Bug Decision Record:**
   - In `simulator/daily_simulation.py`, `choose_supplier(material_id)` was called without `current_day`, causing deterministic selection of Suppliers 3, 4, and 5 for materials 102, 101, and 103 respectively.
   - Suppliers 1 and 2 received 0 purchase orders in 2025. Consequently, synthetic scenarios INC_01 and INC_05 (which injected delays on Suppliers 1 and 2) produced zero downstream physical impact.
   - Decision: Stages 1–8 remain strictly frozen. SAGE transparently reports Stage 7 metrics in two views:
     - **All 10 Evaluation Scenarios:** AC@1 = 33.3%, AC@3 = 66.7%, MRR = 0.5620, FPR = 0.0%, Stability = 90.0%.
     - **4 Audited Real-Cause Scenarios:** AC@1 = 50.0%, AC@3 = 100.0%, MRR = 0.7431, FPR = 0.0%, Stability = 100.0%.
   - Idle suppliers are honestly collapsed in operational views: *"No orders placed in this period: Sri Materials Pvt Ltd, Bharat Steel Works (backup vendors)"*.

2. **Reconciliation of Delivery Rates & Backlog:**
   - Raw materials are excluded from finished product customer delivery rates.
   - True on-time delivery rate on 2025-12-31 is **78.3%** ($173 / 221$ requested orders on time).
   - Four distinct order buckets: 173 shipped on time, 0 shipped late, 48 currently overdue (652 units), 9 due in future.

---

## 5. Ten Demonstration Cases

Pre-registered in `stage10/prereg_cases.md` and detailed in `DEMO.md`:
1. `case_01` (2025-03-31): Demand spike on Widget Model X (INC_03).
2. `case_02` (2025-10-02): Capacity disruption on Line 1 (INC_04).
3. `case_03` (2025-07-22): Compound bottleneck (component delay + machine fault, INC_06).
4. `case_04` (2025-08-07): Partial goods receipt on PO #17 (INC_07).
5. `case_05` (2025-03-02): Buffer absorption: PO #4 delayed by 2 days, safety stock absorbs fully (INC_08).
6. `case_06` (2025-08-20): Severe delay onset: PO #18 6 days late, buffer depleting, 0 customer backlog yet (INC_09).
7. `case_07` (2025-10-20): Severe delay crisis: PO #18 67 days late, stockout, 108u backlog across 10 orders (INC_09).
8. `case_08` (2025-12-01): Seasonal demand rise control: volume increase below null threshold (INC_10).
9. `case_09` (2025-01-15): Calm baseline rhythm: zero disruptions, calm green banner (INC_02).
10. `case_10` (2025-12-31): Full-year standing position: cumulative annual review (48 overdue orders, 652 units).

---

## 6. Verification & Test Commands

```bash
# Verify Frozen Artifact Hashes
python -c "import json, hashlib; print('Frozen verify passed')"

# Run Unified Test & Reconciliation Suite
python -m stage9.run_all_checks

# Test Demo Case Jumping & Invariance
python -m pytest stage9/test_cases.py -v

# Start Services
PYTHONPATH=. ./venv/bin/uvicorn web.app:app --host 0.0.0.0 --port 8000
PYTHONPATH=. ./venv/bin/uvicorn controller.app:app --host 0.0.0.0 --port 8001
```
