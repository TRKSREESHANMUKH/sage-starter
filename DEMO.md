# SAGE — Stage 9 Final 2 Presenter's Sheet: Ten Demo Cases

> **Verbatim Framing Statement:**
> "SAGE performs controlled synthetic causal-attribution evaluation under an expert-defined causal model; it does not claim to prove real-world causality."

---

## Presenter Disclosure & Sourcing-Bug Briefing (Part 1 Record)

Before demonstrating SAGE, ensure you understand the 2025 ERP data topology:
1. **The Supplier Selection Bug:** In the frozen Stage 4 simulation (`simulator/daily_simulation.py`), `choose_supplier(material_id)` was called without passing `current_day`. As a result, the default date seed (`2025-01-01`) was reused on every purchase order generation throughout 2025.
2. **Consequence:** Supplier 4 was deterministically selected for Material 101 (Steel Rod 10mm), Supplier 3 for Material 102 (Plastic Granules), and Supplier 5 for Material 103 (Copper Wire). Suppliers 1 (Sri Materials Pvt Ltd) and 2 (Bharat Steel Works) received zero purchase orders in 2025 and functioned purely as inactive backup vendors.
3. **Synthetic Incidents INC_01 and INC_05:** Because they targeted Suppliers 1 and 2, their injected delays were virtual and produced zero physical disruption on factory operations.
4. **Transparent Two-Way Reporting:**
   - **All 10 scenarios** (treating INC_01 and INC_05 as real causes): AC@1 = 33.3%, AC@3 = 66.7%, MRR = 0.5620, FPR = 0.0%, Stability = 90.0%.
   - **4 physical-cause scenarios** (INC_03, INC_04, INC_06, INC_08, excluding no-effect scenarios): AC@1 = 50.0%, AC@3 = 100.0%, MRR = 0.7431, FPR = 0.0%, Stability = 100.0%.
   - Idle suppliers are honestly collapsed in the UI with the label: *"No orders placed in this period: Sri Materials Pvt Ltd, Bharat Steel Works (backup vendors)"*.

---

## The Ten Demonstration Cases

```
┌─────────┬────────────┬─────────────────────────────┬────────────────────────────────────────────────────────┐
│ Case #  │ Date       │ Scenario                    │ Operational Nature                                     │
├─────────┼────────────┼─────────────────────────────┼────────────────────────────────────────────────────────┤
│ Case 01 │ 2025-03-31 │ Demand Spike (INC_03)       │ Order intake surge on Product 201 (Widget Model X)     │
│ Case 02 │ 2025-10-02 │ Capacity Disruption (INC_04)│ Machine stoppage on Assembly Line 1                    │
│ Case 03 │ 2025-07-22 │ Compound Bottleneck (INC_06)│ Simultaneous component delay & machine maintenance     │
│ Case 04 │ 2025-08-07 │ Partial Receipt (INC_07)    │ Supplier 4 delivers 70% of PO #17; finished in 2 days  │
│ Case 05 │ 2025-03-02 │ Buffer Absorption (INC_08)  │ PO #4 delayed by 2 days, safety stock absorbs fully    │
│ Case 06 │ 2025-08-20 │ Severe Delay Onset (INC_09) │ PO #18 6 days late, buffer depleting, 0 backlog yet   │
│ Case 07 │ 2025-10-20 │ Crisis Peak (INC_09)        │ PO #18 67 days late, stockout, 108u backlog (10 SOs)   │
│ Case 08 │ 2025-12-01 │ Seasonal Demand (INC_10)    │ Expected end-of-year volume rise (control test)        │
│ Case 09 │ 2025-01-15 │ Calm Rhythm (INC_02)        │ Zero disruptions, clean baseline operations            │
│ Case 10 │ 2025-12-31 │ Year-End Standing           │ Full-year cumulative standing (652u backlog, 48 SOs)   │
└─────────┴────────────┴─────────────────────────────┴────────────────────────────────────────────────────────┘
```

---

### Case 1 — 31 March 2025: Demand Spike on Widget Model X (INC_03)
- **Situation:** Customer orders surged on Widget Model X, consuming warehouse stock and creating immediate dispatch urgency.
- **Audience View:**
  - Header: `Demo case 1 of 10 — 31 Mar 2025 (simulated)`.
  - Alert Card: `Customer orders demand surge`.
  - Cause Chain: `Customer demand surge → Finished goods buffer exhausted → Shipment delay`.
  - Evidence: `Seen end to end` (Attribution score: 0.3842 vs null threshold 0.2180).
- **What to Point Out:**
  - Note that raw materials are fully available in the warehouse. SAGE correctly attributes the root driver to customer sales intake rather than a factory floor breakdown.
- **Fallback:** If questioned about supplier delivery status, show Supplier Watch: all three active suppliers are on schedule.

---

### Case 2 — 02 October 2025: Capacity Disruption on Line 1 (INC_04)
- **Situation:** Main drive assembly fault on Assembly Line 1 causes 45 units of lost manufacturing capacity.
- **Audience View:**
  - Alert Card: `Assembly production shortfall (Widget Model X)`.
  - Cause Chain: `Line 1 mechanical fault → Workcenter capacity deficit → Output shortfall`.
  - Evidence: `Seen end to end` (Attribution score: 0.4120).
- **What to Point Out:**
  - Expand "Click to analyze →". Show that material inventory was well above safety stock. The causal engine isolates the internal production node as the sole constraint.
- **Fallback:** Review "Today's Focus": Priority #1 directs maintenance to inspect Line 1 spindle drives.

---

### Case 3 — 22 July 2025: Compound Bottleneck (INC_06)
- **Situation:** Simultaneous material transit delay and secondary line maintenance create a dual bottleneck.
- **Audience View:**
  - Alert Cards: Two concurrent alerts (Material shortage + Production shortfall).
  - Cause Chain: `Component delay + Machine maintenance → Compounded fulfillment bottleneck`.
  - Evidence: `Seen end to end` (Attribution score: 0.4610).
- **What to Point Out:**
  - This demonstrates SAGE's multi-root attribution capability: rather than picking only one cause, both drivers clear the baseline threshold.
- **Fallback:** Show the trailing 30-day sparklines showing concurrent dips.

---

### Case 4 — 07 August 2025: Partial Shipment Receipt (INC_07)
- **Situation:** EastCoast Components delivers 70% of PO #17 (35 of 50 units) on 7 Aug; the remaining 15 units arrive on 9 Aug.
- **Audience View:**
  - Alert Card: `Steel Rod 10mm running low (safety buffer held)`.
  - Evidence: `Seen end to end` (Attribution score: 0.2350).
  - Status Pill: `NEEDS ATTENTION`.
- **What to Point Out:**
  - Explain the partial receipt logic: SAGE detects the 30% short-shipment on goods receipt, alerting managers before downstream assembly is starved.
- **Fallback:** Point to Insights ledger where PO #17 partial fulfillment is logged on 7 Aug and completed on 9 Aug.

---

### Case 5 — 02 March 2025: Buffer Absorption (INC_08)
- **Situation:** PO #4 with EastCoast Components was 2 days overdue, but the warehouse safety stock buffer absorbed the delay completely.
- **Audience View:**
  - Operational Status: `CRITICAL` on raw material stock, but Customer Backlog is `0`.
  - Cause Chain: `PO delay → Raw material buffer drew down → Buffer held → Zero customer backlog`.
  - Evidence: `Seen end to end`.
- **What to Point Out:**
  - Crucial demonstration of buffer awareness: SAGE distinguishes between an operational delay that causes customer harm vs. one absorbed by safety stock. Zero customer orders were late.
- **Fallback:** Check Numbers Strip: `Overdue Orders Now: 0`.

---

### Case 6 — 20 August 2025: Severe Delay Onset (INC_09 Onset)
- **Situation:** EastCoast Components PO #18 is 6 days overdue. Steel Rod stock has fallen near safety threshold, but customer backlogs have not yet started.
- **Audience View:**
  - Alert Card: `Steel Rod 10mm running low (1 open order PO #18 is 6 days overdue)`.
  - Customer Backlog: `0 units`.
  - Priority #1: `Expedite PO #18 with EastCoast Components`.
- **What to Point Out:**
  - Highlight proactive warning: SAGE flags PO #18 six days into the delay, weeks before customer delivery failure occurs.
- **Fallback:** Show "Click to analyze →" sparkline illustrating inventory heading toward the red dotted safety line.

---

### Case 7 — 20 October 2025: Crisis Peak (INC_09 Crisis)
- **Situation:** PO #18 has remained unfulfilled for 67 days. Steel Rod stock is depleted to 9 units (stockout). Widget Model X production has halted and 10 customer sales orders are overdue (108 units backlog).
- **Audience View:**
  - Alert Card: `Customer orders overdue (10 orders, 108 units backlog)` [CRITICAL].
  - Cause Chain: `EastCoast Components delay (PO #18, 67d overdue) → Steel Rod buffer zero → Line starvation → Customer backlog (108u)`.
  - Evidence: `Seen end to end`.
- **What to Point Out:**
  - Contrast with Case 6: this is the full realization of the unmitigated delay. SAGE traces the entire 67-day cascade end to end.
- **Fallback:** Open Today's Focus: Top action assigns Procurement Lead to approve express freight and Production Manager to reschedule shifts.

---

### Case 8 — 01 December 2025: Seasonal Demand Control (INC_10)
- **Situation:** Anticipated end-of-year commercial volume rise on Widget Model Y.
- **Audience View:**
  - Alert Card: `Seasonal demand rise` [WATCH].
  - Evidence: `Seen end to end` (Attribution score: 0.0810, below baseline threshold 0.2180).
- **What to Point Out:**
  - SAGE correctly classifies this as an anticipated calendar volume rise rather than an operational anomaly.
- **Fallback:** Compare with Case 1 (unanticipated spike) to highlight score differences.

---

### Case 9 — 15 January 2025: Calm Rhythm (INC_02 Control)
- **Situation:** Baseline operations with normal production, on-time vendor receipts, and zero customer backlog.
- **Audience View:**
  - Banner: `Everything is running normally`.
  - Subtitle: `Nothing needs action tomorrow`.
  - Numbers Strip: `Overdue Orders: 0`, `Units Short: 0`, `Materials Below Safety: 0`.
  - Supplier Watch: All three active vendors show `Normal operations`.
- **What to Point Out:**
  - The calm-state view proves SAGE does not cry wolf. In the absence of true disruption, it displays a calm green banner with zero false alarms.
- **Fallback:** Verify all metrics in numbers strip show zeros.

---

### Case 10 — 31 December 2025: Full-Year Standing Position
- **Situation:** Year-end standing position reflecting the cumulative operational history of 2025 (48 overdue orders, 652 units backlog).
- **Audience View:**
  - Header: `Demo case 10 of 10 — 31 Dec 2025 (simulated)`.
  - Numbers Strip: `Overdue Orders: 48`, `652 units short`.
  - Insights Tab: Year-to-date customer on-time delivery rate is `78.3%` (173 of 221 requested orders on time).
- **What to Point Out:**
  - Demonstrates full-year continuity. Show the Insights tab to review vendor scorecards and delay ledgers across all 365 days.
- **Fallback:** Use the Controller's "Year review" button if switching from another historical case.
