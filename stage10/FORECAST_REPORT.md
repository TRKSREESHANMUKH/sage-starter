# SAGE Weekly Order Forecast Report (v3 Final)

> SAGE performs controlled synthetic causal-attribution evaluation under an expert-defined causal model; it does not claim to prove real-world causality.

---

## 1. Executive Summary & Pre-Registration Protocol

This report documents the design, rigorous evaluation, and deployment of the **7-Day Forward-Looking Order Forecast** in SAGE. All modeling choices, candidate architectures, selection criteria, and evaluation metrics were **pre-registered** in `stage10/prereg_forecast_v3.md` (committed at `3e63717`) prior to training and testing.

### Key Pre-Registered Specifications:
- **Protocol Document:** `stage10/prereg_forecast_v3.md`
- **Evaluation Split:** 
  - **H1 (2025-01-01 to 2025-06-30):** Model selection via expanding-window Cross-Validation (Sundays $n=21$, with 28-day historical burn-in).
  - **H2 (2025-07-01 to 2025-12-31):** Strictly out-of-sample walk-forward test (Sundays $n=25$; rolling daily $n=177$).
- **Selection Rule:** Lowest WAPE on H1 Cross-Validation.
- **Reporting Rule:** Report all candidates, including underperforming models. No cherry-picking. Report accuracy strictly with metric name and sample size ($n$).

---

## 2. Forecast Targets & Operational Purpose

In supply chain operations, forward-looking visibility requires distinguishing between **orders already on the books** and **new demand expected to arrive**:

1. **Target 1 (Expected New Orders $D+1 \dots D+7$):**
   - Predicted total unit demand arriving in the next 7 calendar days.
   - Broken down into Widget Model X (Product 201), Widget Model Y (Product 202), and Total.
   - Purpose: Informs raw material buffer adequacy, procurement planning, and capacity readiness.
2. **Target 2 (Known Due Orders $D+1 \dots D+7$):**
   - Committed sales orders already received and scheduled for delivery in the next 7 calendar days, extracted directly from the ERP database without forecasting.
   - Purpose: Grounded execution schedule for factory floor and dispatch.

---

## 3. Candidate Models & Selection (H1 Cross-Validation)

Seven pre-registered candidate models were evaluated across 21 expanding-window Sunday test points in H1 2025:

| Model ID | Model Name | Description | CV WAPE ($n=21$) | CV MAE (units) | CV Accuracy ($1-\text{WAPE}$) | CV Bias (units) | CV MASE (vs B1) | Status |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **B1** | Last 7d Total | Naive 7-day persistence | 0.6072 | 34.67 | 39.3% | -2.57 | 1.000 | Baseline |
| **B2** | **Trailing 28d Mean $\times$ 7** | **4-week rolling mean per weekday** | **0.5455** | **31.14** | **45.5%** | **-1.88** | **0.898** | **SELECTED** |
| **B3** | Weekday $\times$ Month Mean | Historical seasonality cell mean | 0.6028 | 34.42 | 39.7% | -9.89 | 0.993 | Baseline |
| **B4** | Zero Forecast | Predicts 0 units every day | 1.0000 | 57.10 | No better than zero | -57.10 | 1.647 | Lower Anchor |
| **M5** | Negative Binomial GLM | Count-data log-linear regression | 0.5976 | 34.12 | 40.2% | -31.39 | 0.984 | Candidate |
| **M6** | Quantile GBDT (HistGBR) | Gradient boosting (10th, 50th, 90th) | 0.5889 | 33.62 | 41.1% | -18.69 | 0.970 | Candidate |
| **M7** | Pipeline-Adjusted Mean | Trailing mean adjusted for open pipeline | 0.5475 | 31.26 | 45.3% | -0.72 | 0.902 | Candidate |

### Selection Outcome:
**Baseline (2): Trailing 28d Mean $\times$ 7** achieved the lowest WAPE (0.5455) and highest accuracy (45.5%) across H1 CV. Per the pre-registered protocol, Model B2 was selected as the deployed production model.

---

## 4. Out-of-Sample Walk-Forward Test (H2 2025)

The selected model and all comparison candidates were frozen and evaluated on strictly unseen out-of-sample data from H2 2025:

### Primary Benchmark: Sunday Horizons ($n=25$)
Evaluated weekly every Sunday across the second half of 2025:

| Model ID | Model Name | Test WAPE ($n=25$) | Test MAE (units) | Test Accuracy ($1-\text{WAPE}$) | Test Bias (units) | Test MASE (vs B1) | 80% CI Coverage |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **B1** | Last 7d Total | 0.8451 | 40.60 | 15.5% | -5.08 | 1.000 | N/A |
| **B2 (Deployed)** | **Trailing 28d Mean $\times$ 7** | **0.6474** | **31.10** | **35.3%** | **-2.42** | **0.766** | N/A |
| **B3** | Weekday $\times$ Month Mean | 0.8156 | 39.18 | 18.4% | -15.16 | 0.965 | N/A |
| **B4** | Zero Forecast | 1.0000 | 48.04 | No better than zero | -48.04 | 1.183 | N/A |
| **M5** | Negative Binomial GLM | 0.6491 | 31.18 | 35.1% | -21.60 | 0.768 | N/A |
| **M6** | Quantile GBDT (HistGBR) | 0.7483 | 35.95 | 25.2% | -0.44 | 0.885 | 64.0% |
| **M7** | Pipeline-Adjusted Mean | 0.6552 | 31.48 | 34.5% | -1.90 | 0.775 | N/A |

### Granular Performance Slices for Deployed Model (B2):

#### 1. By Product ($n=25$ Sundays):
- **Widget Model X (Product 201):** MAE = 21.61 units, WAPE = 0.7922 (Accuracy = 20.8%, Bias = -2.33 units).
- **Widget Model Y (Product 202):** MAE = 14.83 units, WAPE = 0.7144 (Accuracy = 28.6%, Bias = -0.09 units).
- **Total Combined Demand:** MAE = 31.10 units, WAPE = 0.6474 (Accuracy = 35.3%, Bias = -2.42 units).
*Insight:* Portfolio aggregation reduces relative variance; total demand accuracy (35.3%) substantially outperforms individual SKU forecasts (20.8% and 28.6%).

#### 2. Rolling Daily Test ($n=177$ Horizons):
Across all 177 daily walk-forward horizons in H2 2025:
- **MAE:** 30.62 units
- **WAPE:** 0.6312 (Accuracy: **36.9%**)
- **Bias:** -2.67 units

#### 3. Monthly Accuracy Slices (Sundays):
- **July ($n=4$):** WAPE 0.6181 (Accuracy 38.2%, Bias +18.25u)
- **August ($n=5$):** WAPE 0.4138 (Accuracy **58.6%**, Bias -8.80u)
- **September ($n=4$):** WAPE 0.7614 (Accuracy 23.9%, Bias -9.56u)
- **October ($n=4$):** WAPE 0.8913 (Accuracy 10.9%, Bias +12.75u)
- **November ($n=5$):** WAPE 0.6376 (Accuracy 36.2%, Bias -7.70u)
- **December ($n=3$):** WAPE 0.5877 (Accuracy 41.2%, Bias -21.25u)

---

## 5. Theoretical Irreducible Noise Floor (Aleatoric Variance)

A critical scientific question in demand forecasting is: *How good could any model possibly be on this data?*

To answer this, we conducted an independent Monte Carlo audit (`stage10/audit/noise_floor.py`) simulating 100,000 weeks directly from the true underlying data generation process:
- Discrete Bernoulli order arrival ($p=0.42$ per weekday).
- Uniform random customer sampling ($\mathcal{U}[1, 3]$ customers per order).
- Known customer factors ($[1.2, 0.85, 1.35, 1.0, 0.7]$) and weekday multipliers.

### Noise Floor Findings:
- **Mean Weekly Demand:** 49.87 units
- **Weekly Variance (Aleatoric):** 979.01 units$^2$ ($\sigma = 31.29$ units)
- **Oracle Theoretical Minimum MAE:** 25.11 units
- **Oracle Theoretical Minimum WAPE:** **0.5034** (Oracle Accuracy: **49.7%**)

### Scientific Conclusion on Model Performance:
Because daily order arrivals are governed by discrete probabilistic draws, **an omniscient Oracle possessing the exact simulation code and true parameters cannot achieve a WAPE lower than 0.5034 (or accuracy above 49.7%)**. 

The deployed SAGE Model (B2) achieves:
- **Test WAPE:** 0.6474
- **Excess Error over Oracle:** Only **0.1440 WAPE** (5.99 units MAE).
- **Aleatoric Limit Efficiency:** The model captures **77.8% of the theoretical oracle limit**, operating remarkably close to the mathematical noise floor of this manufacturing system.

---

## 6. System Integration & Guardrails

The weekly forecast is fully integrated across the SAGE operational surfaces:
1. **Today Executive Dashboard:** A dedicated "Next 7 days: expected new orders" forward-look card displaying projected demand, committed scheduled orders, shortage risk classification ("Low", "Medium", "High"), 12-week historical trend sparkline, and direct links to the deep-dive benchmark.
2. **Insights & Retrospective View:** Comprehensive "Weekly Order Forward-Look & Model Benchmark" (`#forecast`) containing interactive model comparisons, noise floor explanation, and the 25-week walk-forward audit log.
3. **Daily Executive Email & 1-Page PDF:** Standardized 1-line operational forward-look summary ensuring dispatch briefs remain strictly within the 1-page A4 print budget.
4. **Zero Look-Ahead & Idempotency:**
   - Stored walk-forward predictions for past days reflect strictly the data available as of that morning.
   - Future days are blocked with plain-English notices ("That day has not happened yet in this demo").
   - Dry-run operations strictly protect the delivery log from unauthorized SMTP transmissions.

---

## 7. Model Artifact Details
- **Serialized Artifact:** `stage10/forecast/model.pkl` (and `stage10/forecast/outputs/model_v3.pkl`)
- **Artifact SHA256:** `a6b37c2e1558f1138a8e1165db602ec3ffc8de37a627fe01e6e37d1de427c6ab`
- **Output Audit Files:**
  - `stage10/forecast/outputs/test_weekly_forecasts.json` (walk-forward logs)
  - `stage10/forecast/outputs/metrics.json` (evaluation metrics)
  - `stage10/forecast/outputs/noise_floor.json` (aleatoric noise floor simulation)
