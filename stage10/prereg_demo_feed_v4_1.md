# SAGE — Stage 10 Pre-Registration v4.1: Calibrated Ten-Day Simulation Feed Protocol

> **Mandatory Scientific Framing:**  
> "SAGE performs controlled synthetic causal-attribution evaluation under an expert-defined causal model; it does not claim to prove real-world causality."

---

## 1. Revision Notice (v4.1)
* **Registration Timestamp:** 2026-11-01T05:10:00+00:00
* **Reason for Revision:**
  - In initial v4 generation, Day 1 demand for Widget Model X totaled 22 units, exceeding the 10-unit surge threshold and triggering an elevated demand intake alert (`WATCH`) instead of routine baseline (`NORMAL`). Day 1 intake is calibrated to 9 units (<10 units) across 3 orders to ensure baseline operations.
  - In initial v4 generation, Day 9 demand totaled 22 units for Model X and 17 units for Model Y, which filled alert slots with demand intake cards and suppressed the `Standing customer backlog clearing` alert. Day 9 order intake is calibrated to standard Friday baseline (9 units Model X, 8 units Model Y) so that the carried-over backlog burn-down card surfaces with `NEEDS_ATTENTION`.
  - All physical scenario rules, opening positions, and unhedged tier predictions remain identical to v4.

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
- **PARTIAL**: Expected entity is identified in the alerts, but the actual tier differs by exactly one level.
- **MISS**: Expected entity is not identified OR tier is off by two or more levels OR unexpected false alarm.
- Labelled strictly as: *"Rehearsal on a designed feed, not validation"*.
