# SAGE — Stage 10 Pre-Registration v3: Ten-Day Scripted Demo Feed Protocol (1–10 January 2026)

> **Mandatory Scientific Framing:**  
> "SAGE performs controlled synthetic causal-attribution evaluation under an expert-defined causal model; it does not claim to prove real-world causality."

---

## 1. Post-Hoc Disclosure & Version 3 Notice
* **Registration Timestamp:** 2026-10-24T09:20:00+00:00
* **Disclosure Notice:** This version 3 protocol supersedes `prereg_demo_feed_v2.md` and `prereg_demo_feed.md` following exhaustive forensic review of the demo feed generation and scoring engine.
* **Pre-Execution Changes Made Before Feed Regeneration:**
  1. **Day 3 (PO #19 Expected Date):** PO #19 expected delivery date set to `2026-01-02` (was `2026-01-03`). Under end-of-day operational semantics, an order expected today is not overdue; shifting to 2 Jan ensures it is 1 day overdue on 3 Jan, correctly identifying EastCoast Components delivery delay as the primary operational trigger while steel stock holds.
  2. **Day 6 vs Day 7 Headline Separation:** Day 6 steel stock finishes at 47 kg (above 0 kg, but at/below safety stock of 50 kg), producing the headline `Steel Rod 10mm at safety stock (47 kg remaining) — EastCoast Components PO #19 overdue` (CRITICAL). Day 7 steel stock drops to 0 kg (stockout), producing the headline `Raw material stockout on Steel Rod 10mm (0 kg in stock)` (CRITICAL).
  3. **Day 4 Reconciled Scope:** Day 4 reflects both a 60% partial receipt from Global Polymers Co (PO #20: 150 of 250 units) and ongoing drawdown of the steel buffer with PO #19 overdue.
  4. **Day 9 Control Day Scoring Alignment:** Day 9 evaluates a seasonal Friday demand surge during active backlog burn-down. Because standing backlog is burning down without new shocks, the operational status is `NEEDS_ATTENTION` (or `WATCH` for volume monitoring). A HIT requires identifying the operational state without triggering a false alarm or CRITICAL tier.

---

## 2. Pre-Registered Predictions for Days 1–10

| Day | Date | Operational Scenario Description | Expected Banner | Expected Root Alert Headline | Expected Entity & Trigger | Expected Focus Action |
| :---: | :---: | :--- | :--- | :--- | :--- | :--- |
| **1** | 2026-01-01 | Normal operations: routine orders, production, shipping | NORMAL | None (All normal) | Normal operations; 0 alerts | Routine shift review |
| **2** | 2026-01-02 | Demand spike on Widget Model X (~2.5x normal), stock covers | WATCH | Elevated demand intake (Widget Model X surge) | Product 201 demand surge | Monitor buffer depletion |
| **3** | 2026-01-03 | Steel delivery (Supplier 4, PO #19) 1d overdue; buffer holds | NEEDS_ATTENTION | Overdue delivery from EastCoast Components (PO #19) | Supplier 4 delivery overdue | Expedite PO #19 delivery |
| **4** | 2026-01-04 | Plastic granules (Supplier 3, PO #20) arrives 60% partial; steel PO #19 2d late | NEEDS_ATTENTION | Partial delivery from Global Polymers Co (PO #20) / Overdue Steel | Supplier 3 partial receipt (150/250u) & Supplier 4 delay | Track plastic balance & expedite steel |
| **5** | 2026-01-05 | Capacity bottleneck on Line 2; Widget Model Y output -50% below plan | NEEDS_ATTENTION | Production below plan (Widget Model Y shortfall) | Line 2 capacity / production shortfall | Rebalance Line 2 assembly |
| **6** | 2026-01-06 | Steel 4d late, steel at safety buffer (47 kg), production cut, backlog onset | CRITICAL | Steel Rod 10mm at safety stock (47 kg remaining) — EastCoast Components PO #19 overdue | Supplier 4 delay -> Steel at safety -> Backlog rising | Prioritize customer shipments & expedite steel |
| **7** | 2026-01-07 | Steel stockout (0 kg), Widget Model X halted, overdue backlog escalating | CRITICAL | Raw material stockout on Steel Rod 10mm (0 kg in stock) | Material 101 stockout -> Line 1 halt -> Rising backlog | Emergency steel sourcing & dispatch review |
| **8** | 2026-01-08 | Steel arrives 5d late in full; production restarts; plastic balance arrives | NEEDS_ATTENTION | Standing customer backlog clearing (recovery in progress) | Recovery in progress; standing backlog not rising | Maximize shift throughput to clear backlog |
| **9** | 2026-01-09 | Friday seasonal demand peak (control day); backlog continuing to burn down | NEEDS_ATTENTION / WATCH | Seasonal throughput monitoring (no disruption) | Control day; seasonal volume; no false alarm | Maintain standard shipping cadence |
| **10** | 2026-01-10 | Dual independent issues: Widget Y -20% and late plastic reorder (PO #22) | NEEDS_ATTENTION | Production below plan / Supplier 3 delay (PO #22) | Line 2 throughput deficit & PO #22 late | Line 2 audit & vendor follow-up |

---

## 3. Strict Deterministic Scoring Rules (`score.py`)

Every day is scored by an automated script (`stage10/demo_feed/score.py`) into exactly one of three categories:

1. **HIT**:
   - Banner tier strictly matches expected tier (or acceptable adjacent pre-registered tier, e.g. `NEEDS_ATTENTION`/`WATCH` on Day 9).
   - Primary alert headline identifies the correct operational root cause entity (Supplier, Workcenter/Product line, or Material).
   - Control day (Day 9) generates NO Critical alert and NO false alarm.

2. **PARTIAL**:
   - Primary alert correctly identifies the entity or operational trigger, but banner tier differs by one level (e.g. `NEEDS_ATTENTION` vs `WATCH`).
   - OR banner tier matches but secondary trigger is ranked over primary.

3. **MISS**:
   - Complete failure to identify the primary root driver.
   - OR control day (Day 9) generates a Critical alert / false alarm.
   - OR completely incorrect root attribution.
