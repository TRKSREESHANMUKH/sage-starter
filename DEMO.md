# SAGE — Stage 9 FINAL 3 Presenter's Sheet: Ten-Day Demo Feed (1–10 January 2026)

> **Verbatim Framing Statement:**
> "SAGE performs controlled synthetic causal-attribution evaluation under an expert-defined causal model; it does not claim to prove real-world causality."

---

## Part 1: Executive Disclosure & Sourcing-Bug Briefing

Before starting the live demonstration, state the following foundational data facts clearly:
1. **The Supplier Selection Bug:** In the frozen Stage 4 simulation (`simulator/daily_simulation.py`), `choose_supplier(material_id)` was called without passing `current_day`. As a result, the default date seed (`2025-01-01`) was reused on every purchase order generation throughout 2025.
2. **Consequence:** Supplier 4 was deterministically selected for Material 101 (Steel Rod 10mm), Supplier 3 for Material 102 (Plastic Granules), and Supplier 5 for Material 103 (Copper Wire). Suppliers 1 (Sri Materials Pvt Ltd) and 2 (Bharat Steel Works) received zero purchase orders in 2025 and functioned purely as inactive backup vendors.
3. **Synthetic Incidents INC_01 and INC_05:** Because they targeted Suppliers 1 and 2, their injected delays produced zero physical disruption on factory operations.
4. **Transparent Two-Way Reporting:**
   - **All 10 scenarios** (treating INC_01 and INC_05 as real causes): AC@1 = 33.3%, AC@3 = 66.7%, MRR = 0.5620, FPR = 0.0%, Stability = 90.0%.
   - **4 physical-cause scenarios** (INC_03, INC_04, INC_06, INC_08, excluding no-effect scenarios): AC@1 = 50.0%, AC@3 = 100.0%, MRR = 0.7431, FPR = 0.0%, Stability = 100.0%.
   - Idle suppliers are honestly collapsed in the UI with the label: *"No orders placed in this period: Sri Materials Pvt Ltd, Bharat Steel Works (backup vendors)"*.
5. **Expert Graph Allowance:** *"The expert graph allows supplier links that the simulated sourcing never used."* Cause-chain tracing dynamically restricts traversal to active supplier links verified in historical purchase orders.
6. **Opening Position:** The 2025 run ended in an unreceived steel PO and standing backorders. On 2025-12-31, stale backorders and PO #18 were cancelled, stock counts adjusted to normal operating levels, and 3 seed POs placed in December. The live database strictly equals main Postgres up to 2025-12-20.

---

## Ten-Day Demonstration Overview (1–10 January 2026)

```
┌──────┬────────────┬─────────────────────────────┬────────────────────────────────────────────────────────┐
│ Day  │ Date       │ Scenario                    │ Operational Nature                                     │
├──────┼────────────┼─────────────────────────────┼────────────────────────────────────────────────────────┤
│ D-01 │ 2026-01-01 │ Normal Operations           │ Routine orders, production, and shipping; calm baseline│
│ D-02 │ 2026-01-02 │ Demand Spike (Widget X)     │ Surge in Widget X orders (2.5x); stock buffer absorbs  │
│ D-03 │ 2026-01-03 │ Supplier 4 Steel Delayed    │ PO #19 due today does not arrive; buffer holds above SS│
│ D-04 │ 2026-01-04 │ Partial Receipt & Delay     │ Plastic PO #20 arrives 60% partial; steel 1d overdue   │
│ D-05 │ 2026-01-05 │ Line Capacity Bottleneck    │ Line 2 downtime; Widget Model Y output 50% below plan  │
│ D-06 │ 2026-01-06 │ Compound Disruption Onset   │ Steel 3d late, steel at safety, 1st customer orders late│
│ D-07 │ 2026-01-07 │ Crisis: Steel Stockout      │ Steel at 0 kg, Widget X halted, mounting backlog       │
│ D-08 │ 2026-01-08 │ Inbound Recovery            │ Steel arrives 5d late, production restarts, backlog clears│
│ D-09 │ 2026-01-09 │ Seasonal Peak (Control)     │ Normal Friday volume bump; backlog continues clearing  │
│ D-10 │ 2026-01-10 │ Dual Unrelated Issues       │ Widget Y -20% and late plastic reorder; unmerged alerts│
└──────┴────────────┴─────────────────────────────┴────────────────────────────────────────────────────────┘
```

---

## Detailed Day-by-Day Presenter Walkthrough

### Day 1: Thursday, 1 January 2026 — Normal Operations
* **What audience sees:** Off-white briefing page with "All operations normal" calm status. Zero alert cards. "Nothing needs action tomorrow". Numbers strip shows steady baseline metrics.
* **What to point out:** Point out the clean editorial layout, serif typography, 90–120 word narrative summary explaining stable factory status, and the upcoming deliveries expected in the next 3 days.
* **If system says something different:** If a Watch alert appears on routine order variance, explain that SAGE runs continuous statistical checks against the 365-day baseline, and minor daily volume variations remain safely within non-critical noise bounds.

### Day 2: Friday, 2 January 2026 — Demand Spike on Widget Model X
* **What audience sees:** Watch / Attention banner. Alert card highlighting an order surge on Widget Model X (~2.5x normal daily orders). Finished goods inventory strip decreases but remains positive.
* **What to point out:** SAGE flags demand anomalies before stockouts happen. The cause chain explains that finished goods safety buffers are currently holding the line.
* **If system says something different:** If the system reports Needs Attention rather than Watch, state that the 2.5x multiplier crossed the volume warning threshold, but note that the critical stockout alert is suppressed because stock remains healthy.

### Day 3: Saturday, 3 January 2026 — Inbound Supplier Delay (Buffer Holding)
* **What audience sees:** Watch alert for overdue steel delivery from Supplier 4 (EastCoast Components, PO #19). Raw material steel stock remains well above safety stock (100 kg).
* **What to point out:** Notice that PO #19 was due today and did not arrive. SAGE detects this supplier delay immediately, but calculates that current inventory covers ongoing manufacturing runs without an immediate production cut.
* **If system says something different:** If no alert is triggered, explain that the supplier delay is within the promised lead-time grace window and is monitored under "Supplier Watch".

### Day 4: Sunday, 4 January 2026 — Partial Goods Receipt & Continuing Delay
* **What audience sees:** Needs Attention banner. Partial delivery alert on Global Polymers Co (PO #20): 150 of 250 kg received (60% fill rate). Supplier 4 steel delivery is now 1 day overdue.
* **What to point out:** Click on the Insights tab to show the supplier scorecard: PO #20 shows "first delivery: 60% of the order; balance expected Jan 8". SAGE tracks partial receipts distinctly from total fulfillment.
* **If system says something different:** Point out that tracking both fill rate and elapsed overdue days gives operations teams early warning before assembly lines starve.

### Day 5: Monday, 5 January 2026 — Production Capacity Disruption
* **What audience sees:** Needs Attention banner. Alert card: "Widget Model Y production below plan". Machine stoppage on Line 2 caused output to drop 50% below daily plan.
* **What to point out:** Click "Click to analyze →" on the alert card. Show the 3 steps: What we saw (production run chart), How it connects (capacity bottleneck rather than raw material shortage), and How sure are we (evidence score).
* **If system says something different:** Emphasize that SAGE distinguishes between capacity disruptions (equipment downtime) and supply shortages (material starvation).

### Day 6: Tuesday, 6 January 2026 — Compound Disruption & Backlog Onset
* **What audience sees:** Critical banner. Compound alert: Supplier 4 steel delivery is 3 days overdue, steel stock reaches safety stock threshold (100 kg), Widget Model X manufacturing is throttled, and the first customer orders become overdue. Copper delivery (PO #21) arrives on time in full.
* **What to point out:** Today's Focus Band highlights prioritized customer orders with order numbers, customer names, units short, and days late.
* **If system says something different:** Emphasize that when inbound delays deplete buffer stock to safety levels, upstream supply issues propagate downstream into customer service failures.

### Day 7: Wednesday, 7 January 2026 — Severe Disruption (Stock-out Peak)
* **What audience sees:** Critical banner. Severe stockout alert: Steel Rod 10mm reaches 0 kg, Widget Model X production completely halted, and overdue customer orders escalate.
* **What to point out:** Show the cause-chain narrative: `Supplier 4 Delay (PO #19) -> Steel Stockout -> Line 1 Stoppage -> Customer Backlog Escalation`.
* **If system says something different:** State that Day 7 represents the peak crisis phase of the synthetic disruption scenario.

### Day 8: Thursday, 8 January 2026 — Inbound Recovery & Production Restart
* **What audience sees:** Needs Attention / Improving status. Inbound arrival: PO #19 steel (400 kg) arrives 5 days late in full. PO #20 plastic balance (100 kg) arrives. Widget Model X production restarts at maximum throughput, burning down overdue orders.
* **What to point out:** Notice the recovery projection: SAGE estimates backlog clearance time based on daily production capacity.
* **If system says something different:** Explain that the transition from Critical to Improving occurs as soon as the root constraint (steel availability) is relieved.

### Day 9: Friday, 9 January 2026 — Seasonal Demand Peak (Control)
* **What audience sees:** Calm / Improving status. Friday customer order volume rises ~25% matching standard weekly seasonality. Backlog continues burning down. Zero false alarms.
* **What to point out:** This is a negative control test. SAGE's expert causal model recognizes regular calendar seasonality and does not trigger an erroneous supply disruption alert.
* **If system says something different:** Emphasize that preventing false alarms during routine peak cycles is essential for operational trust.

### Day 10: Saturday, 10 January 2026 — Dual Independent Minor Issues
* **What audience sees:** Needs Attention banner. Two separate unmerged alerts: 1) Widget Model Y minor production drop (-20%); 2) Supplier 3 plastic reorder PO #22 late. Customer backlog from the earlier crisis is nearly cleared.
* **What to point out:** Notice that SAGE presents two separate cards ranked by operational severity, rather than conflating unrelated supply and assembly issues into a single artificial chain.
* **If system says something different:** Reiterate that maintaining independent causal chains prevents misleading root-cause conclusions.

---

## Presentation Controls & Operator Commands

1. **Start SAGE Servers (Localhost Only):**
   ```bash
   ./run_sage.sh
   ```
   * Live Viewer: `http://127.0.0.1:8000`
   * Controller: `http://127.0.0.1:8001`

2. **Controller Token:**
   * Found in `.env` under the variable `SAGE_CONTROLLER_TOKEN` (never read or display the secret value to the audience).

3. **Feeding Next Day:**
   * In the Controller UI under **Demo Feed**, click **"Feed next day"** once per scenario day.
   * The live briefing viewer auto-refreshes within 5 seconds without manual page reload.

4. **Reset Demo Feed:**
   * Click **"Reset demo feed"** in the Controller to restore the clean 2025-12-31 baseline position in under 30 seconds.
