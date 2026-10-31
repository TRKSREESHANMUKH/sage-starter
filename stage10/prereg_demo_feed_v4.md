# SAGE — Stage 10 Pre-Registration v4: Redesigned Ten-Day Simulation Feed Protocol (1–10 January 2026)

> **Mandatory Scientific Framing:**  
> "SAGE performs controlled synthetic causal-attribution evaluation under an expert-defined causal model; it does not claim to prove real-world causality."

---

## 1. Notice of Pre-Registration (v4)
* **Registration Timestamp:** 2026-10-31T18:10:00+00:00
* **Pre-Registration Status:** COMMITTED STRICTLY PRIOR TO GENERATION RUN of the redesigned 10-day feed.
* **Context & Purpose:** This version 4 pre-registration replaces previous gated versions for the 10-day simulation feed. It pre-registers single, unhedged expected tiers and root drivers derived strictly from the redesigned narrative arc before observing any simulation or product execution outputs.
* **Honesty Rules:**
  - Single expected tier per day (no hedged ranges or A/B alternatives).
  - Tiers are pre-declared based on the physical design:
    - Day 1: Normal operations -> `NORMAL`
    - Day 2: Visible Model X demand surge absorbed by finished goods -> `WATCH`
    - Day 3: Steel PO #19 slips past expected date, buffer holds -> `NEEDS_ATTENTION`
    - Day 4: Partial plastic receipt (PO #20) + steel PO #19 still late -> `NEEDS_ATTENTION`
    - Day 5: Production shortfall on Widget Model Y (capacity drop) -> `NEEDS_ATTENTION`
    - Day 6: Steel inventory at safety stock (50 kg) -> `CRITICAL`
    - Day 7: Steel stockout (0 kg) with real late customer shipments -> `CRITICAL`
    - Day 8: Emergency steel delivery arrives (PO #19 received), recovery begins, carried-over backorders start shipping -> `NEEDS_ATTENTION`
    - Day 9: Friday demand peak cleanly handled, carried-over backorders continue clearing oldest-first -> `NEEDS_ATTENTION`
    - Day 10: Mostly recovered, remaining backorders cleared, minor line variance -> `NEEDS_ATTENTION`

---

## 2. Pre-Registered Predictions for Days 1–10 (Single Tier per Day)

| Day | Date | Operational Scenario Description | Pre-Registered Tier | Expected Main Driver & Root Cause | Pre-Registered Top Alert Theme |
|:---:|:---:|:---|:---:|:---|:---|
| **1** | 2026-01-01 | Baseline healthy operations: steady demand, on-time shipping, healthy stock | **NORMAL** | Normal baseline (no disruptions) | No active alerts (normal operations) |
| **2** | 2026-01-02 | Demand surge on Widget Model X; stock covers volume | **WATCH** | Finished goods demand surge (Product 201) | Elevated demand intake (Widget Model X surge) |
| **3** | 2026-01-03 | Steel PO #19 slips past expected delivery date; buffer absorbs deficit | **NEEDS_ATTENTION** | Supplier 4 (EastCoast Components) delivery delay | Overdue delivery from EastCoast Components (PO #19) |
| **4** | 2026-01-04 | Partial delivery of plastic granules (PO #20) + steel PO #19 still late | **NEEDS_ATTENTION** | Supplier 3 partial receipt & Supplier 4 ongoing delay | Partial delivery from Global Polymers Co (PO #20) / Overdue Steel |
| **5** | 2026-01-05 | Workcenter 2 bottleneck; Widget Model Y output below plan | **NEEDS_ATTENTION** | Assembly capacity constraint on Line 2 (Model Y) | Production below plan (Widget Model Y shortfall) |
| **6** | 2026-01-06 | Steel stock drops to safety stock (50 kg); production throttled | **CRITICAL** | Raw material safety stock breach (Material 101) | Steel Rod 10mm at safety stock (PO #19 overdue) |
| **7** | 2026-01-07 | Steel stockout (0 kg); Model X halted; genuine late customer shipments | **CRITICAL** | Raw material stockout (Material 101) & delayed orders | Raw material stockout on Steel Rod 10mm |
| **8** | 2026-01-08 | Steel PO #19 delivered in full; production restarts; backorders start shipping | **NEEDS_ATTENTION** | Inbound recovery & standing backlog clearing | Standing customer backlog clearing (recovery in progress) |
| **9** | 2026-01-09 | Friday demand peak absorbed; carried-over backlog continues shipping oldest-first | **NEEDS_ATTENTION** | High volume handled; backlog burn-down continuing | Standing customer backlog clearing / Friday volume |
| **10** | 2026-01-10 | Final carried-over orders completed; minor line variance | **NEEDS_ATTENTION** | Recovery consolidated; normal operations restored | Normalizing operations / minor throughput shortfall |

---

## 3. Strict Scoring Rules (`score.py`)

- **HIT**: Actual banner tier exactly matches the pre-registered single tier AND the expected entity is identified in the top-ranked alerts.
- **PARTIAL**: Expected entity is identified in the alerts, but the actual tier differs by exactly one level (e.g. `NEEDS_ATTENTION` vs `WATCH`).
- **MISS**: Expected entity is not identified OR tier is off by two or more levels OR unexpected false alarm.
- Labelled strictly as: *"Rehearsal on a designed feed, not validation"*.
