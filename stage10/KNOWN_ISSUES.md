# SAGE — Known Issues and Audit Findings

> **Research Framing**:
> *"SAGE performs controlled synthetic causal-attribution evaluation under an expert-defined causal model; it does not claim to prove real-world causality."*

---

### Issue 1: The Sourcing Assignment Bug in Routine PO Generation

* **Severity**: Moderate (Impacts Scenario Testing Breadth; Core Mathematics & Methodology Intact).
* **Location**: [`simulator/daily_simulation.py#L316`](file:///Users/asl/Desktop/sage-starter/simulator/daily_simulation.py#L316) and [`simulator/daily_simulation.py#L977`](file:///Users/asl/Desktop/sage-starter/simulator/daily_simulation.py#L977).
* **Status**: Documented; Frozen Stages 1–8 Preserved (Future Work, Not Done).

#### Root Cause Proof
1. The function signature is `def choose_supplier(material_id, current_day=date(2025, 1, 1)):`.
2. At the reorder call site in line 977: `supplier_id = choose_supplier(material_id)`, the `current_day` parameter was omitted.
3. Because `current_day` defaulted to `2025-01-01` on every call throughout the year, the deterministic random number generator (`get_deterministic_rng("choose_supplier", date(2025, 1, 1), material_id)`) produced the exact same index draw on every single call:
   * Material 101 (Steel Rod 10mm, choices `[1, 2, 4]`): returned Supplier 4 (EastCoast Components) on 10 of 10 purchase orders.
   * Material 102 (Plastic Granules, choices `[3, 4]`): returned Supplier 3 (Global Polymers Co) on 4 of 4 purchase orders.
   * Material 103 (Copper Wire, choices `[1, 5]`): returned Supplier 5 (Copper & Co) on 4 of 4 purchase orders.
4. No other routine code path assigned vendors. As a result, Supplier 1 (Sri Materials Pvt Ltd) and Supplier 2 (Bharat Steel Works) received **0 purchase orders** throughout the entire 2025 simulation.

#### Consequences for Designed Incidents INC_01 and INC_05
* **Incident INC_01** (`supplier_delay` on Supplier 1, `2025-08-17` to `2025-08-18`): Supplier 1 had no open or planned purchase orders in 2025. The delay shifted an exogenous inbound variable in the simulation logs, but delayed zero physical deliveries and zero inventory units.
* **Incident INC_05** (`overlapping_supplier_delay` on Supplier 1 and Supplier 2, `2025-10-16` to `2025-10-23`): Neither supplier had active purchase orders. Zero physical units were delayed.
* **Effect on Causal Evaluations**: Incidents INC_01 and INC_05 never produced a true physical supply chain disruption. In causal attribution, they scored as unattributed / below null threshold.

#### Causal Benchmark Two-Way Reporting (Stage 7 Evaluation)
Because INC_01 and INC_05 did not constitute valid stress tests, we report the Stage 7 benchmark metrics under both conventions:

| Metric | Originally Reported (All 10 Scenarios) | Reclassified (Excluding INC_01 & INC_05) | Source File |
| :--- | :---: | :---: | :--- |
| **Attribution Accuracy @ 1 (AC@1)** | **33.3%** (2 of 6 real-cause) | **50.0%** (2 of 4 real-cause) | `analytics/scenario_causal_evaluation.json` |
| **Attribution Accuracy @ 3 (AC@3)** | **66.7%** (4 of 6 real-cause) | **100.0%** (4 of 4 real-cause) | `analytics/scenario_causal_evaluation.json` |
| **Mean Reciprocal Rank (MRR)** | **0.5620** | **0.7431** | `analytics/scenario_causal_evaluation.json` |
| **False Positive Rate (FPR)** | **0.0%** | **0.0%** | `analytics/scenario_causal_evaluation.json` |
| **Stability Pass Rate** | **90.0%** (9 of 10 seeds) | **100.0%** (4 of 4 real-cause) | `analytics/scenario_causal_evaluation.json` |

*Limitation Statement*: "Two of the ten designed scenarios did not produce an effect because of a sourcing bug found in our own audit. The results above are reported with and without them."

#### Remediation Plan (Future Work — Stages 1–8 Kept Frozen)
To avoid breaking the frozen research foundation (which would invalidate all downstream panels, causal pickle artifacts, and preregistered tests), the simulation was not re-run. Future iterations will pass `current_day` into `choose_supplier` or implement an explicit multi-sourcing quota rule, followed by a full refit of the causal model.

---

### Issue 2: Expert Graph (DAG) Sourcing Allowance vs Actual Simulation Routing

* **Description**: The Stage 7 expert DAG defines theoretical potential supply links:
  * Material 101 $\leftarrow$ Suppliers 1, 2, 4
  * Material 102 $\leftarrow$ Suppliers 3, 4
  * Material 103 $\leftarrow$ Suppliers 1, 5
* **Reality**: The simulation routed 100% of Material 101 to Supplier 4, Material 102 to Supplier 3, and Material 103 to Supplier 5.
* **Project Action**: Documented limitation on the Method page: *"The expert graph allows supplier links that the simulated sourcing never used."* Stage 9 cause-chain tracing dynamically filters edges to active supplier links verified in the historical data.

---

### Issue 3: Incident INC_08 Entity Label in `business_events`

* **Description**: In `simulator/incidents.yaml`, INC_08 is defined as delay absorbed by safety stock on Supplier 5 for Material 103. In the database `business_events` table (Event #1), it was logged with `entity_type: supplier, entity_id: 4`.
* **Resolution**: Documented as a frozen metadata discrepancy. Handled transparently by tracing actual purchase order lines.

---

### Issue 4: Customer Backlog Reconciled Across Sources (Part R1 & R2)

* **Description**: An apparent contradiction arose between the live database holding 48 overdue customer orders (652 units) at year-end, while the baseline panel (`daily_panel.parquet`) showed 0 backlog units throughout the year.
* **Resolution**:
  1. `daily_panel.parquet` (sha256: `ba6f33c0...`) is the frozen *null baseline* run (zero incidents injected), which appropriately holds 0 due backlog.
  2. `daily_panel_ext.parquet` (sha256: `2de6861f...`) represents the *scenario incident run*, which records exactly 652 units of due backlog on 2025-12-31 (Product 201: 475u, Product 202: 177u), matching the database and `snapshot.py` to the exact unit.
  3. Total customer orders requested $\le$ 2025-12-31: 221 orders. 173 were shipped on time, 0 shipped late, 2 partially shipped and overdue, and 46 unshipped and overdue (total 48 overdue orders).
  4. Across the entire simulation, 57 orders experienced backorders (48 requested in 2025 + 9 requested in 2026), matching Stage 4 simulator statistics (`orders_ever_backordered = 57`) exactly.

---

### Issue 5: EastCoast Components PO #18 (Material 101) Stuck Order (Part R3)

* **Description**: PO #18 (placed 2025-08-05, expected 2025-08-14, 407 units of Steel Rod 10mm) received zero goods receipts through 2025-12-31 (139 days overdue).
* **Investigation & Cause**:
  1. Ground-truth incident INC_09 (`severe_supplier_delay` on Supplier 4 from 2025-08-05 to 2026-01-18) delayed delivery by 166 days.
  2. The simulation MRP logic calculated `inventory_position = on_hand + on_order`. Because PO #18 remained open with 407 units on order, the inventory position remained above the reorder point, so no additional POs were generated.
* **Classification**: PO #18 is a real stuck order produced by a frozen ground-truth stress incident, not an artifact or data error. All screens display it accurately as `139 days overdue (was due 14 Aug 2025)`.
* **Date Difference Reconciliation**:
  - Exact DB PO #18: Placed `2025-08-05`, expected `2025-08-14`. Overdue days as of 2025-12-31 = 139 days.
  - Incident INC_09 Duration: Disruption window opened on `2025-07-18`, giving 166 days elapsed to year end.

---

### Issue 6: Eventful-Date Scan vs Year-End Overdue Orders (Gate A4)

* **Description**: The earlier eventful-date scan found no problem days after 2025-10-15, yet 48 orders were overdue at year end (63 units on 2025-10-20, rising to 652 units on 2025-12-31).
* **Investigation & Cause**:
  1. The eventful-date scan inspected the baseline null panel (`daily_panel.parquet`) where backorders are 0 throughout the year.
  2. The scan also specifically looked for incident initiation dates (the latest incident, INC_09, began on or before 2025-10-15).
  3. In the scenario panel (`daily_panel_ext.parquet`) and live database, the operational downstream consequence (depleted finished goods buffer and cascading customer backorders) persisted continuously through December 31.
* **Resolution**: Causal evaluation correctly references `daily_panel_ext.parquet`, capturing both the incident triggers and the enduring downstream backorders.

---

### Issue 7: Simulator Backorder Settlement Limitation (Late-But-Delivered is Zero by Construction)

* **Description**: In the simulator engine (`simulator/daily_simulation.py`), customer order shipments are evaluated exclusively on their requested delivery date. If stock is insufficient, available units are delivered, and the balance is marked `Backorder`.
* **Mechanical Finding**: The simulator contains no retroactive shipment sweep for aged backorders once their requested date has passed. Consequently, orders that encounter stockouts remain permanently backordered rather than being fulfilled late.
* **Impact**: Across all 221 customer orders requested on or before 2025-12-31, "Shipped Complete AFTER Requested Date" is strictly **0**. Late deliveries manifest entirely as open standing backlog.

---

### Issue 8: Post-Hoc Disclosure — Ten-Day Demo Feed Rules v2 & Standing Backlog Decoupling

* **Disclosure Date**: 2026-10-23
* **Context**: Review of initial demo feed execution revealed that treating any positive standing backlog (`due_backlog_units > 0`) as `CRITICAL` caused the operational status banner to stay pegged at Critical on Days 2, 3, and 8, and produced a false alarm on Day 9 (the pre-registered seasonal control day).
* **Remediation**: Transitioned from raw numeric backlog thresholding to structural operational conditions (codified in `stage9/config/rules.yaml` and `stage10/prereg_demo_feed_v2.md`):
  1. **CRITICAL**: Requires an active material stockout (0 units), OR material at/below safety stock with an overdue PO, OR customer backlog units rising vs yesterday with a traced cause.
  2. **NEEDS ATTENTION**: Assigned when standing backlog is steady or burning down, an overdue PO exists, or production is below plan.
  3. **WATCH**: Assigned for elevated customer demand intake or partial goods receipts.
  4. **NORMAL**: Operations within standard tolerances; no active daily disruptions.
  5. Backlog is documented as a consequence line inside the root-cause alert card rather than a separate lead card.
* **Results Table Before vs After**: Documented in the Master Final Report and `stage10/demo_feed_results.md`.
