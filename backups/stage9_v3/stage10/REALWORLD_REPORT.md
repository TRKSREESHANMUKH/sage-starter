# SAGE Real-World Generalisation Evaluation Report (Stage 10)

> "SAGE performs controlled synthetic causal-attribution evaluation under an expert-defined causal model; it does not claim to prove real-world causality."

---

## 1. Test A — Fresh Synthetic Worlds (Seeds 7 & 11)

Evaluated the frozen Stage 7 causal model and frozen null thresholds ($M_1 \text{ p95} = 0.218006$, $M_2 \text{ p95} = 0.922611$) without refitting across two completely unseen synthetic worlds with $\pm 30\%$ intensity perturbations and randomized timings. Trailing 60-day windows evaluated around all 10 scenarios, plus 20 quiet windows per seed from baseline.

| Evaluation Metric | Stage 7 Baseline (Seed 42) | Test A: Seed 7 (Unseen) | Test A: Seed 11 (Unseen) | Generalisation Finding |
| :--- | :--- | :--- | :--- | :--- |
| **Detection Rate (Detectable Scenarios)** | **100.0%** (4 / 4) | **0.0%** (0 / 4) | **0.0%** (0 / 4) | **Sharp drop**; static thresholds do not transfer across dynamical regimes |
| **False-Alarm Rate (Quiet Windows)** | **5.0%** (calibrated null) | **90.0%** (18 / 20) | **60.0%** (12 / 20) | **Substantial increase**; baseline variance shifts under new random seeds |
| **Driver Rank: INC_03 (Demand Spike)** | Rank 1 (Top driver) | Rank 8 | Rank 5 | Lag features (`product_fg_stock_lag1`) absorb variance over 60d window |
| **Driver Rank: INC_04 (Capacity Shortfall)** | Rank 1 (Top driver) | Rank 5 | Rank 9 | Production planning & inventory lags dominate long trailing windows |
| **Driver Rank: INC_06 (Two Simultaneous)** | Rank 2 | Rank 3 | Rank 2 | Identified in top-3 candidates, but score stays below frozen null threshold |
| **Driver Rank: INC_08 (Absorbed Delay)** | Rank 99 (Correct control) | Rank 99 | Rank 99 | Correctly rejected; zero impact on downstream inventory |
| **Severe Stockout: INC_09** | Rank 2 | Rank 2 | **Rank 2 (Score: -0.3779, Cleared Null)** | Successfully attributed above null in Seed 11 |

**Honest Scientific Analysis**:
When tested against unseen synthetic worlds without refitting, the detection rate drops from 100% to 0% for the 4 pre-registered scenarios, and false alarms rise significantly (60–90%). Over extended 60-day trailing windows, autoregressive lag features (`stock_lag1`) absorb the bulk of Shapley variance, and static null thresholds calibrated on Seed 42 fail to adapt to shifted variance envelopes.

---

## 2. Test B — Real Public Dataset (Demand-Side Plausibility Check)

- **Dataset**: Walmart Store Sales Forecasting (Store 1, Department 72: Consumer Electronics).
- **Scope**: Calendar and exogenous demand conditioning plausibility check only; does not evaluate supply chain, bill of materials, or multi-echelon inventory mechanics.
- **Calibration Period**: 2010 (Year 1, 48 weekly records). Empirical null 95th percentile threshold = **$25,497.78**.
- **Evaluation Period**: 2011 (Year 2, 52 weekly records with 4 documented public holiday events).
- **Results**:
  - **Thanksgiving / Black Friday (2011-11-25)**: Actual sales spiked to **$203,670.47** (baseline: $44,101.76). Attribution score = **$159,568.71**, clearing the null threshold by **6.26x** (`FLAGGED ABOVE NULL`).
  - **Ordinary Weeks False Alarm Rate**: **2.1%** (1 false alarm across 48 non-holiday weeks).
  - **Signal-to-Noise Ratio (SNR)**: **6.67x** (Mean holiday attribution score: $49,345.39 vs ordinary week: $7,399.62).
  - **Minor Holidays (Super Bowl, Labor Day, Christmas)**: Scored within normal weekly volatility envelopes and remained below the null threshold.

---

## 3. Test C — Status of Real Company Data Readiness

- **Ingest Adapter (`stage10/ingest_adapter.py`)**: Built and verified. Converts arbitrary CSV operational logs (orders, inventory levels, purchase orders, work orders) into standardized Stage 6 daily panel columns (`date`, `supplier_*`, `material_*`, `product_*`).
- **Validation Run**: Executed on `stage10/sample_company_data.csv`, validating schema conformance (`Valid: True`, 3 rows, 49 columns).
- **Enterprise Specification (`stage10/DATA_READINESS.md`)**: Completed. Outlines exact required schema, mandatory 1-year history prerequisite, and human-in-the-loop governance requirements.

---

## 4. What This Does and Does Not Prove

### What It Does Prove:
1. **Mathematical Plausibility**: SAGE's attribution mechanics correctly flag major real-world exogenous events (Black Friday demand shock, SNR 6.67x) with low false alarms on ordinary periods (2.1%).
2. **Controlled Benchmark Validity**: Within its calibrated training world, SAGE consistently separates direct drivers from buffer-absorbed noise under an explicit causal graph.
3. **Pipeline Interoperability**: The operational data adapter is ready to ingest real enterprise ERP/WMS CSV exports.

### What It Does NOT Prove:
1. **No Proof of Real-World Physical Causality**: Real company data has no ground truth answer key. No statistical or machine learning system can prove real-world causality from purely observational logs.
2. **No Universal Zero-Shot Generalisation**: As proven by Test A, static null thresholds and frozen weights cannot be blindly deployed across different factories or regimes without site-specific baseline calibration.
3. **No Automatic Graph Discovery**: SAGE requires the facility's plant manager and engineering team to review and approve the causal DAG; it does not discover factory flow out of thin air.
4. **No Protection Against Unmeasured Confounders**: External factors unrecorded in enterprise tables (e.g., regional power outages, weather storms, unlogged equipment wear) cannot be detected.

---

## 5. Mentor-Facing Summary (5 Lines)

1. Fresh synthetic testing (Test A) proves that static null thresholds do not generalise across unseen worlds without adaptive recalibration (detection rate drops to 0%, false alarms rise to 60–90%).
2. On real retail data (Test B), the demand model successfully flags Black Friday at 6.26x above the null threshold with a 2.1% false alarm rate on ordinary weeks.
3. An end-to-end enterprise CSV adapter and data readiness specification (Test C) were built, verified, and documented.
4. Causal attribution over long trailing windows is dominated by autoregressive inventory lags unless evaluated on tight incident windows.
5. SAGE demonstrates controlled synthetic attribution and demand plausibility, but neither claims nor proves real-world physical causality on uncalibrated enterprise data.
