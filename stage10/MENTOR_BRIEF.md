# SAGE — Executive Mentor Briefing (Stage 10 Final Close-Out)

> **Mandatory Scientific Framing Statement:**  
> *"SAGE performs controlled synthetic causal-attribution evaluation under an expert-defined causal model; it does not claim to prove real-world causality."*

---

### 1. Evaluation Parameters & Foundational Scope
- **Domain:** Discrete manufacturing assembly and customer order fulfillment supply chain.
- **Data Period:** Complete 2025 simulated annual baseline (365 calendar days) and 10-day live demonstration feed (1–10 January 2026).
- **Core Scope:** SAGE continuously cross-checks incoming operational telemetry against physical constraints (Bills of Materials, lead times, inventory safety buffers) and scores causal attribution under an expert-defined Directed Acyclic Graph (DAG). SAGE evaluates synthetic causal-attribution performance; it does not claim to prove real-world causality.

---

### 2. Seasonality & Lag Limits
- **Seasonality Handling:** Order arrival is intermittent and zero-inflated: **68.2% of calendar days** (249 of 365 days) have zero customer orders placed. Weekly aggregation smooths daily Bernoulli sparsity, while monthly volume progression is tracked via trailing 28-day windows.
- **Physical Response Lags & Limits:**
  - Across the 10 designed incidents, the median physical lag from inbound purchase order delay to raw material safety stock breach is **5.5 days** (individual lags: 8, 0, 172, 3 days; derived from **$n=4$ observations** due to the sourcing bug leaving Suppliers 1 and 2 idle).
  - The lag from raw stockout to customer shipment backlog is immediate (**0 days**, **$n=1$ observation** from INC_06).
  - **INC_07 Unattributable:** An isolated capacity bottleneck without upstream material starvation; because finished goods buffers partially absorbed the disruption, the anomaly remained within normal operational variance and was unattributable upstream.
  - **INC_09 Lag Dominance:** A multi-month buffer cushion (172-day lag) decoupled the initial supplier delay from subsequent material depletion, illustrating the temporal boundary of 7-day rolling trace windows.

---

### 3. Stress Test & Attribution Integrity
- **Attribution Count Integrity:** In the 92-day stress evaluation window, SAGE produced **3 false attributions out of 92 days** (96.7% attribution specificity; 3.3% false attribution count).
- **Lag Sample Sizes:** Reported response lags are transparently qualified by tiny sample sizes: **$n=4$** for PO delay to safety stock breach, and **$n=1$** for safety stock breach to customer backorder.
- **Historical Tier Distribution:** The full 365-day historical index contains **124 Normal, 49 Watch, 38 Needs attention, and 154 Critical days**. Aug–Dec 2025 is mostly Critical due to PO #18 (407 units raw steel) remaining unreceived (139 days overdue) with open backlog, which SAGE tracked faithfully without post-hoc threshold loosening.

---

### 4. Weekly Forecast Honesty (Protocol v4)
- **Deployed Architecture:** Trailing 28-day Mean $\times$ 7 (selected via lowest Cross-Validation WAPE of **0.5455 [CV]** / **45.5% [CV]** accuracy on H1 2025; $n=21$ Sunday test points).
- **Model Comparison:** Gradient boosting and count regression did not outperform the trailing mean on this single-year simulated dataset due to high intermittency (68.2% zero-order days).
- **Attribution of Accuracy Gain:**
  - While apparent accuracy for total weekly demand due is **68.5%** (WAPE **0.3152 [TEST]** on 25 Sundays, MAE 14.22u, Bias -0.18u; WAPE **0.2540 [TEST]** on 177 daily windows, MAE 11.66u, Bias -0.32u), **headline accuracy is driven almost entirely by the ERP order book**: a trivial booked-only baseline achieves **68.0% accuracy** (WAPE 0.3200 [TEST] on Sundays; WAPE 0.2381 [TEST] daily).
  - Forecasting unbooked new orders alone ($S(D)$) remains noisy with WAPE **0.9848 [TEST]** on Sundays and WAPE **1.0668 [TEST]** daily, compared to the theoretical Oracle irreducible noise floor of WAPE **0.5034 [ORACLE]**.

---

### 5. Ten-Day Demonstration Feed Rehearsal
- **Design:** Deterministically scripted scenarios with a 1-day customer lead time (contrasting with 2025 historical median of 6.0 days) to test immediate operational response.
- **Order-Rate Ratio:** Demo feed order rate is elevated: ~7.3 units/day (2025 baseline requested) vs ~14.6 units/day (demo days, 2.0x units ratio), and ~0.63 orders/day (2025) vs 2.2 orders/day (demo days, 3.5x order-count ratio). Demo-day forward looks demonstrate live software operation and rolling buffer sizing under live inputs; they are not an accuracy test.
- **Honest Scoring Tallies (score.py):**
  - **v1 Original Pre-registration (`a31aef9`):** **6 HITS (60.0%)**, **2 PARTIALS (20.0%)**, **2 MISSES (20.0%)**.
  - **v2 Intermediate Pre-registration (`cfa45f2`):** **8 HITS (80.0%)**, **0 PARTIALS (0.0%)**, **2 MISSES (20.0%)**.
  - **v3 Rehearsal (`a38b8fd`):** **9 HITS (90.0%)**, **0 PARTIALS (0.0%)**, **1 MISS (10.0%)**.  
  *Disclosure: Version 3 expectations were written after seeing results (rehearsal, not validation).*
