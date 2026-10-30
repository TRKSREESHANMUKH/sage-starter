# SAGE — Known Issues & Scientific Limitations

> **Mandatory Scientific Framing Statement:**  
> *"SAGE performs controlled synthetic causal-attribution evaluation under an expert-defined causal model; it does not claim to prove real-world causality."*

---

## 1. Simulation & Sourcing Limitations

### 1.1 Inactive Backup Suppliers in 2025 Baseline
* **Description:** In the frozen Stage 4 simulation (`simulator/daily_simulation.py`), the supplier selection routine `choose_supplier(material_id)` was called without passing the simulation date parameter. As a result, the default timestamp (`2025-01-01`) was reused for every purchase order generation throughout 2025.
* **Operational Effect:** Routine purchase orders were deterministically routed to three active vendors: Supplier 4 (EastCoast Components, Steel Rod), Supplier 3 (Global Polymers Co, Plastic Granules), and Supplier 5 (Copper & Co, Copper Wire). Suppliers 1 (Sri Materials Pvt Ltd) and 2 (Bharat Steel Works) received zero orders during 2025.
* **Evaluation Impact:** Injected delay incidents targeting Suppliers 1 and 2 (INC_01 and INC_05) produced zero operational disruption. SAGE honestly reports metrics across all 10 cohorts (AC@1 = 33.3%) as well as the 4 physically active disruption cohorts (AC@1 = 50.0%, AC@3 = 100.0%). In the user interface, idle backup vendors are clearly grouped with transparent disclosure.

### 1.2 Backorder Settlement Semantics
* **Description:** In the baseline simulation, customer sales orders evaluate delivery strictly on their customer-requested delivery date. Orders unfulfilled on that date transition to a standing backorder rather than shipping on subsequent days.
* **Operational Effect:** Backorders accumulate until cancelled or cleared during explicit recovery scenarios. On 2025-12-31, exactly 48 stale sales orders (652 units) and PO #18 (407 units) were cancelled to establish a clean operational baseline for the 2026 demonstration feed.

---

## 2. Demonstration Feed Design vs Historical Realities

### 2.1 Lead-Time Design Difference
* **Historical Baseline (2025):** Customer sales orders operate with a lead time of 3 to 10 days, with a median of 6.0 days.
* **Demonstration Feed (2026):** Customer sales orders were scripted with a 1-day lead time (`lead_d = 1`) by design to create immediate pressure and allow complete order-to-delivery cycles, stockouts, and backlog clearance to be demonstrated within 10 calendar days.
* **Disclosure:** Demonstration feed tiers reflect deterministic response to scripted inputs, not predictive accuracy.

### 2.2 Rehearsal Status of Pre-Registration v3
* **Description:** Pre-registration version 3 (`stage10/prereg_demo_feed_v3.md`) was finalized after observing feed rehearsal outputs to refine operational definitions (e.g. distinguishing safety-stock breach on Day 6 from raw stockout on Day 7).
* **Disclosure:** Version 3 represents rehearsal rather than blind prospective validation. Prospective performance is honestly reflected in original v1 (7/10 HITS, 3 PARTIALS, 0 MISSES) and v2 (9/10 HITS, 1 PARTIAL, 0 MISSES).

---

## 3. Demand Forecasting Boundaries

### 3.1 Order Book Driving Headline Accuracy
* **Finding:** Apparent forecast accuracy on units due ($D+1 \dots D+7$) reaches 68.5% (0.3152 WAPE [TEST] on Sundays; 0.2540 WAPE [TEST] daily).
* **Limitation:** Between 68.0% and 76.2% of due demand is already booked in the ERP database on origin day $D$. The predictive model adds only the marginal difference. A trivial model predicting only known booked orders achieves 68.0% accuracy (0.3200 WAPE [TEST]).

### 3.2 High Intermittency and Irreducible Noise Floor
* **Intermittency:** 68.2% of calendar days in 2025 have zero incoming sales orders placed.
* **Noise Floor:** Monte Carlo analysis establishes that an omniscient Oracle knowing the true stochastic data generation process cannot achieve a WAPE lower than 0.5034 [ORACLE] on unbooked demand. Predicting the unknown part $S(D)$ alone remains noisy (WAPE ~0.98 on Sundays, ~1.07 daily).

---

## 4. Platform Safety & Execution Invariants

1. **Email Safety Invariant:** SAGE operates strictly in DRY-RUN mode by default. Switching to LIVE mode requires an explicit modal confirmation by typing `LIVE`. All automated test suites enforce mock SMTP transports with 0 live sends.
2. **Server Binding:** Both Viewer (port 8000) and Controller (port 8001) bind exclusively to `127.0.0.1` (localhost only).
3. **Database Immutability:** Stages 1–8 and the main PostgreSQL database remain strictly read-only and frozen. Demo feed operations execute against the isolated `live/sage_live.db` SQLite database.
