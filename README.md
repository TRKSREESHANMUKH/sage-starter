# SAGE — Strategic Analytics for Guided Execution

> **Mandatory Scientific Framing:**  
> *"SAGE performs controlled synthetic causal-attribution evaluation under an expert-defined causal model; it does not claim to prove real-world causality."*

SAGE is a causal decision-intelligence and operations evaluation platform designed for discrete manufacturing and fulfillment supply chains. It continuously cross-checks incoming operational telemetry against physical constraints (Bills of Materials, lead times, workcenter capacities) and computes causal attribution scores under an expert-defined Directed Acyclic Graph (DAG).

---

## Ten-Day Demonstration Feed Evaluation (1–10 January 2026)

> **Evaluation Honesty & Rehearsal Disclosure:**  
> The ten evaluation days are scripted; tiers matching the script show that the product responds faithfully to operational inputs, not that it predicts the future. Customer orders placed in the 2026 demo feed operate with a 1-day lead time by design to create immediate pressure, contrasting with the 2025 historical data where lead times had a median of 6 days (range 3–8 days). Version 3 expectations were written after seeing results (rehearsal, not validation). Scored against original v1 expectations, SAGE achieves **7/10 HITS (70.0%)**, 3 PARTIALS (30.0%), and 0 MISSES. Against rehearsal v3 expectations, SAGE scores **10/10 HITS (100.0%)** (or 9/10 if Day 9 is strictly evaluated against WATCH).

| Day | Date | Operational Scenario | v1 Expected | v2 Expected | v3 Expected (Rehearsal) | Actual Tier | v1 Score | v3 Score |
| :---: | :---: | :--- | :--- | :--- | :--- | :--- | :---: | :---: |
| **D-01** | 2026-01-01 | Normal operations baseline | NORMAL | NORMAL | NORMAL | NORMAL | HIT | HIT |
| **D-02** | 2026-01-02 | Demand spike (Widget Model X surge) | WATCH | WATCH | WATCH | WATCH | HIT | HIT |
| **D-03** | 2026-01-03 | Steel PO #19 delayed (buffer holds) | WATCH | NEEDS_ATTENTION | NEEDS_ATTENTION | NEEDS_ATTENTION | PARTIAL | HIT |
| **D-04** | 2026-01-04 | Partial plastic receipt & steel late | NEEDS_ATTENTION | NEEDS_ATTENTION | NEEDS_ATTENTION | NEEDS_ATTENTION | HIT | HIT |
| **D-05** | 2026-01-05 | Capacity disruption (Line 2 bottleneck) | NEEDS_ATTENTION | NEEDS_ATTENTION | NEEDS_ATTENTION | NEEDS_ATTENTION | HIT | HIT |
| **D-06** | 2026-01-06 | Steel at safety stock, backlog onset | CRITICAL | CRITICAL | CRITICAL | CRITICAL | HIT | HIT |
| **D-07** | 2026-01-07 | Crisis: Steel stockout, assembly halt | CRITICAL | CRITICAL | CRITICAL | CRITICAL | HIT | HIT |
| **D-08** | 2026-01-08 | Inbound arrival, recovery in progress | IMPROVING | NEEDS_ATTENTION | NEEDS_ATTENTION | NEEDS_ATTENTION | PARTIAL | HIT |
| **D-09** | 2026-01-09 | Friday seasonal demand peak (control) | NORMAL / CALM | NORMAL / CALM | NEEDS_ATTENTION | NEEDS_ATTENTION | PARTIAL | HIT |
| **D-10** | 2026-01-10 | Dual unrelated operational alerts | NEEDS_ATTENTION | NEEDS_ATTENTION | NEEDS_ATTENTION | NEEDS_ATTENTION | HIT | HIT |

---

## Key Scientific Disclosures
1. **Fulfillment Definition:** An order is on time if and only if it is shipped complete on or before its customer-requested delivery date; unfulfilled orders and orders encountering stockout remain in open backlog and are classified as not on time.
2. **Opening Baseline:** Evaluated from an audited 31 Dec 2025 opening position where 48 stale 2025 backorders (652 units) and PO #18 (407 units) were cancelled, and raw inventory stood at 215 kg Steel, 204 kg Plastic, and 184 meters Copper.
3. **Forecasting Protocol v4:** The deployed weekly forecast model is a trailing 28-day mean (lowest CV WAPE 0.55 [CV]). GBDT and count regression did not beat it due to 68.2% zero-order days (249 of 365 calendar days).
4. **Historical Tier Breakdown:** The 365-day historical index contains 124 Normal, 49 Watch, 38 Needs attention, and 154 Critical days.
