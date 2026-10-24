# SAGE — Owner's Live Demo Checklist & Quick Reference

> **Mandatory Scientific Framing Statement:**  
> *"SAGE performs controlled synthetic causal-attribution evaluation under an expert-defined causal model; it does not claim to prove real-world causality."*

---

## 1. Pre-Flight Setup (5 minutes before meeting)

- [ ] **Docker Container Check:** Ensure PostgreSQL is running:
  ```bash
  docker ps | grep sage_postgres
  ```
  *(Port: 5433 -> 5432, container healthy).*

- [ ] **Run Full Verification Check:**
  ```bash
  ./verify_all.sh
  ```
  *(Takes ~25s; must end with `✓ ALL VERIFICATION CHECKS PASSED SUCCESSFULLY (Exit 0)`).*

- [ ] **Start SAGE Servers:**
  ```bash
  ./run_sage.sh
  ```
  *(Starts Executive Viewer on `127.0.0.1:8000` and Operator Controller on `127.0.0.1:8001` in DRY-RUN mode).*

- [ ] **Open Browser Tabs:**
  1. **Executive Dashboard (Viewer):** [http://127.0.0.1:8000/](http://127.0.0.1:8000/) (Sign in using `SAGE_WEB_TOKEN` from `.env`)
  2. **Operator Control Panel (Controller):** [http://127.0.0.1:8001/ctrl/login](http://127.0.0.1:8001/ctrl/login) (Sign in using `SAGE_CONTROLLER_TOKEN` from `.env`)
  3. **Insights Tab:** [http://127.0.0.1:8000/insights](http://127.0.0.1:8000/insights)
  4. **Method & Governance Tab:** [http://127.0.0.1:8000/method](http://127.0.0.1:8000/method)

---

## 2. Walkthrough Sequence for Mentor Presentation

### A. Foundational Honesty & Ground Truth (Method Tab)
- [ ] Show the **Method Tab** ([http://127.0.0.1:8000/method](http://127.0.0.1:8000/method)).
- [ ] Point out the **Mandatory Scientific Framing** banner.
- [ ] Highlight the **Synthetic Causal Attribution Cohorts** table:
  * **All 10 Scenarios:** Hit@1 = 40.0%, Hit@3 = 60.0%, MRR = 0.5622
  * **Excluding Sourcing Bug (8 scenarios):** Hit@1 = 50.0%, Hit@3 = 75.0%, MRR = 0.6528
  * **Original Stage 7 Benchmark (6 scenarios):** Hit@1 = 33.3%, Hit@3 = 66.7%, MRR = 0.5620
  * **Physical-Cause Scenarios (4 scenarios):** Hit@1 = 50.0%, Hit@3 = 100.0%, MRR = 0.7431
- [ ] Disclose the **Simulator Settlement Limitation**: Late-but-delivered orders are 0 by construction because the simulator fulfills strictly on requested dates with no retroactive shipment sweep.

### B. Operations Insights & Data Validity (Insights Tab)
- [ ] Show the **Insights Tab** ([http://127.0.0.1:8000/insights](http://127.0.0.1:8000/insights)).
- [ ] Point out the **Demo Baseline Notice**: *"Opening position set on 31 Dec 2025 for the demo: 48 unfulfilled 2025 customer orders and purchase order #18 were cancelled and raw material stock adjusted, so the ten-day feed starts from a clean position."*
- [ ] Point out the **Four Fulfillment Buckets**:
  * **On-time complete:** 173 orders (1,981 units) — 78.3% on-time delivery rate.
  * **Shipped late:** 0 orders (0 units) — by simulator construction.
  * **Partly shipped:** 2 orders (19 shipped, 4 open units — SO #164 & SO #184).
  * **Unshipped:** 46 orders (648 open units).
  * **Total unfulfilled:** 48 orders (652 open units).
- [ ] Show **Supplier Scorecards**:
  * **EastCoast Components:** Shows PO #18 as 139 days overdue (was due 2025-08-14) stuck order.
  * **Copper & Co:** Shows PO #17 partial receipt: first receipt 105 of 150 units (70%), completed 2 days after first delivery.
  * **Idle Backup Vendors:** Sri Materials Pvt Ltd and Bharat Steel Works honestly collapsed into a single line: *"No orders placed in this period: Sri Materials Pvt Ltd, Bharat Steel Works (backup vendors)"*.

### C. Live Ten-Day Feed Demonstration (Controller -> Viewer)
- [ ] Reset demo to Day 0 opening position via controller button **Reset to 31 Dec 2025**.
- [ ] Advance day by day (Days 1 through 10) clicking **Feed Next Day**:
  * **Day 1 (1 Jan):** Normal operations, green calm banner, no alerts, 90–120 word narrative.
  * **Day 2 (2 Jan):** Demand spike on Widget Model X (~2.5x volume), buffer holds.
  * **Day 3 (3 Jan):** EastCoast steel delivery PO #19 overdue, inventory buffer holds above safety.
  * **Day 4 (4 Jan):** Global Polymers plastic PO #20 arrives 60% partial (150/250 kg); steel remains overdue.
  * **Day 5 (5 Jan):** Machine capacity downtime on Line 2 (Widget Model Y production 50% below plan).
  * **Day 6 (6 Jan):** Compound disruption: steel reaches safety buffer (100 kg), customer backorders begin.
  * **Day 7 (7 Jan):** Crisis peak: steel stockout (0 kg), Widget Model X halted, overdue customer orders escalate.
  * **Day 8 (8 Jan):** Inbound recovery: PO #19 arrives 5 days late in full, assembly restarts, backlog burns down.
  * **Day 9 (9 Jan):** Seasonal peak (Friday control day): volume bump handled normally without false alarms.
  * **Day 10 (10 Jan):** Dual independent minor issues (Line 2 minor dip and late plastic reorder).

### D. Automated Replay & Verification Proof
- [ ] Demonstrate that the scoring engine evaluates all 10 days deterministically:
  ```bash
  ./venv/bin/python stage10/demo_feed/score.py
  ```
  *(Result: 6 Hits, 4 Partials, 0 Misses).*
- [ ] Demonstrate safe dry-run email dispatch:
  ```bash
  ./venv/bin/python -m stage9.send_check
  ```
  *(Status: SUCCESS_DRY_RUN; zero email leakage to Gmail).*

---

## 3. Teardown / Clean Exit

- [ ] Stop SAGE servers cleanly:
  ```bash
  ./stop_sage.sh
  ```
  *(Verifies ports 8000 and 8001 are free).*
