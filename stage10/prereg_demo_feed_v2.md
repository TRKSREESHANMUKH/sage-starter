# SAGE — Stage 10 Pre-Registration v2: Ten-Day Scripted Demo Feed Protocol (1–10 January 2026)

> **Mandatory Scientific Framing:**  
> "SAGE performs controlled synthetic causal-attribution evaluation under an expert-defined causal model; it does not claim to prove real-world causality."

---

## 1. Post-Hoc Disclosure & Version 2 Notice
* **Registration Timestamp:** 2026-10-23T06:50:00+00:00
* **Disclosure Notice:** This version 2 protocol supersedes `prereg_demo_feed.md` following review of the initial test results. The initial rules evaluated standing cumulative backlog as a constant critical state, which prevented operational differentiation on Days 2, 3, and 8, and caused a false alarm on Day 9 (the control day). 
* **Structural Principles:** The rules below replace numeric thresholds with structural conditions:
  1. A standing unchanged backlog does NOT keep the operational banner Critical.
  2. Banner tiers reflect new or worsening operational shocks:
     - **CRITICAL**: A raw material stock-out (0 units), OR raw material at/below safety stock with an overdue PO, OR overdue customer backlog units rising vs yesterday with a traced cause.
     - **NEEDS ATTENTION**: Standing overdue backlog not rising, an overdue PO, or production below plan.
     - **WATCH**: Elevated customer demand intake or a partial goods receipt.
     - **NORMAL**: All daily flows within standard parameters.
  3. Alert cards represent root causes, with customer backlogs presented as downstream consequences inside the cause card, rather than a separate lead card crowding out production or supply issues.
  4. Cause chains are generated solely from active traces; if no upstream root is identified, the chain states "No upstream explanation found".
  5. The model check line is displayed only when an active model check ran; otherwise "Model check not run for this day".

---

## 2. Pre-Registered Predictions for Days 1–10

| Day | Date | Operational Scenario Description | Expected Banner | Expected Root Alert Headline | Expected Entity & Trigger | Expected Focus Action |
| :---: | :---: | :--- | :--- | :--- | :--- | :--- |
| **1** | 2026-01-01 | Normal operations: routine orders, production, shipping | NORMAL | None (All normal) | Normal operations; 0 alerts | Routine shift review |
| **2** | 2026-01-02 | Demand spike on Widget Model X (~2.5x normal), stock covers | WATCH | Elevated demand intake (Widget Model X) | Product 201 demand surge | Monitor buffer depletion |
| **3** | 2026-01-03 | Steel delivery (Supplier 4, PO #19) does not arrive; buffer holds | NEEDS_ATTENTION | Overdue delivery from EastCoast Components (PO #19) | Supplier 4 delivery overdue | Expedite PO #19 delivery |
| **4** | 2026-01-04 | Plastic granules (Supplier 3, PO #20) arrives 60% partial; steel PO #19 1d late | NEEDS_ATTENTION | Partial delivery from Global Polymers Co (PO #20) / Overdue Steel | Supplier 3 partial receipt (150/250u) & Supplier 4 delay | Track plastic balance & expedite steel |
| **5** | 2026-01-05 | Capacity bottleneck on Line 2; Widget Model Y output -50% below plan | NEEDS_ATTENTION | Production below plan (Widget Model Y shortfall) | Line 2 capacity / production shortfall | Rebalance Line 2 assembly |
| **6** | 2026-01-06 | Steel 3d late, steel at safety buffer, production cut, customer orders delayed | CRITICAL | Steel buffer depleted at safety threshold / Backlog onset | Supplier 4 delay -> Steel at safety -> Backlog rising | Prioritize customer shipments & expedite steel |
| **7** | 2026-01-07 | Steel stockout (0 kg), Widget Model X halted, overdue backlog escalating | CRITICAL | Material stockout on Steel Rod 10mm (0 units in stock) | Material 101 stockout -> Line 1 halt -> Rising backlog | Emergency steel sourcing & dispatch review |
| **8** | 2026-01-08 | Steel arrives 5d late in full; production restarts; plastic balance arrives | NEEDS_ATTENTION | Standing customer backlog clearing / Delivery recovery | Recovery in progress; standing backlog not rising | Maximize shift throughput to clear backlog |
| **9** | 2026-01-09 | Friday seasonal demand peak (control day); backlog continuing to burn down | NORMAL / WATCH | Seasonal throughput monitoring (no disruption) | Control day; seasonal volume; no false alarm | Maintain standard shipping cadence |
| **10** | 2026-01-10 | Dual independent issues: Widget Y -20% and late plastic reorder (PO #22) | NEEDS_ATTENTION | Dual separate alerts: Production shortfall & Supplier 3 delay | Line 2 throughput deficit & PO #22 late | Line 2 audit & vendor follow-up |

---

## 3. Strict Deterministic Scoring Rules (`score.py`)

Every day is scored by an automated script (`stage10/demo_feed/score.py`) into exactly one of three categories:

1. **HIT**:
   - Banner tier strictly matches expected tier (or acceptable adjacent pre-registered tier, e.g. Normal/Watch on Day 9).
   - Primary alert headline identifies the correct operational root cause entity (Supplier, Workcenter/Product line, or Material).
   - Control day (Day 9) generates NO Critical or false alarm alert.

2. **PARTIAL**:
   - Primary alert correctly identifies the entity or operational trigger, but banner tier differs by one level (e.g. Needs Attention vs Watch).
   - OR banner tier matches but one secondary issue is not highlighted in top 2 cards.

3. **MISS**:
   - Complete failure to identify the primary root driver.
   - OR control day (Day 9) generates a Critical alert / false alarm.
   - OR completely incorrect root attribution.
