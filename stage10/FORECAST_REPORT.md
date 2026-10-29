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

Seven pre-registered candidate models were evaluated across 21 expanding-window Sunday test points in H1 2025 (all metrics marked `[CV]`):

| Model ID | Model Name | Description | CV WAPE [CV] ($n=21$) | CV MAE [CV] (units) | CV Accuracy [CV] ($1-\text{WAPE}$) | CV Bias [CV] (units) | CV MASE [CV] (vs B1) | Status |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **B1** | Last 7d Total | Naive 7-day persistence | 0.6072 [CV] | 34.67 [CV] | 39.3% [CV] | -2.57 [CV] | 1.000 [CV] | Baseline |
| **B2** | **Trailing 28d Mean $\times$ 7** | **4-week rolling mean per weekday** | **0.5455 [CV]** | **31.14 [CV]** | **45.5% [CV]** | **-1.88 [CV]** | **0.898 [CV]** | **SELECTED** |
| **B3** | Weekday $\times$ Month Mean | Historical seasonality cell mean | 0.6028 [CV] | 34.42 [CV] | 39.7% [CV] | -9.89 [CV] | 0.993 [CV] | Baseline |
| **B4** | Zero Forecast | Predicts 0 units every day | 1.0000 [CV] | 57.10 [CV] | No better than zero | -57.10 [CV] | 1.647 [CV] | Lower Anchor |
| **M5** | Negative Binomial GLM | Count-data log-linear regression | 0.5976 [CV] | 34.12 [CV] | 40.2% [CV] | -31.39 [CV] | 0.984 [CV] | Candidate |
| **M6** | Quantile GBDT (HistGBR) | Gradient boosting (10th, 50th, 90th) | 0.5889 [CV] | 33.62 [CV] | 41.1% [CV] | -18.69 [CV] | 0.970 [CV] | Candidate |
| **M7** | Pipeline-Adjusted Mean | Trailing mean adjusted for open pipeline | 0.5475 [CV] | 31.26 [CV] | 45.3% [CV] | -0.72 [CV] | 0.902 [CV] | Candidate |

### Selection Outcome:
**Baseline (2): Trailing 28d Mean $\times$ 7** achieved the lowest WAPE (0.5455 [CV]) and highest accuracy (45.5% [CV]) across H1 CV. Per the pre-registered protocol, Model B2 was selected as the deployed production model.

---

## 4. Out-of-Sample Walk-Forward Test (H2 2025)

The selected model and all comparison candidates were frozen and evaluated on strictly unseen out-of-sample data from H2 2025 (all metrics marked `[TEST]`):

### Primary Benchmark: Sunday Horizons ($n=25$)
Evaluated weekly every Sunday across the second half of 2025:

| Model ID | Model Name | Test WAPE [TEST] ($n=25$) | Test MAE [TEST] (units) | Test Accuracy [TEST] ($1-\text{WAPE}$) | Test Bias [TEST] (units) | Test MASE [TEST] (vs B1) | 80% CI Coverage [TEST] |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **B1** | Last 7d Total | 0.8451 [TEST] | 40.60 [TEST] | 15.5% [TEST] | -5.08 [TEST] | 1.000 [TEST] | N/A |
| **B2 (Deployed)** | **Trailing 28d Mean $\times$ 7** | **0.6474 [TEST]** | **31.10 [TEST]** | **35.3% [TEST]** | **-2.42 [TEST]** | **0.766 [TEST]** | N/A |
| **B3** | Weekday $\times$ Month Mean | 0.8156 [TEST] | 39.18 [TEST] | 18.4% [TEST] | -15.16 [TEST] | 0.965 [TEST] | N/A |
| **B4** | Zero Forecast | 1.0000 [TEST] | 48.04 [TEST] | No better than zero | -48.04 [TEST] | 1.183 [TEST] | N/A |
| **M5** | Negative Binomial GLM | 0.6491 [TEST] | 31.18 [TEST] | 35.1% [TEST] | -21.60 [TEST] | 0.768 [TEST] | N/A |
| **M6** | Quantile GBDT (HistGBR) | 0.7483 [TEST] | 35.95 [TEST] | 25.2% [TEST] | -0.44 [TEST] | 0.885 [TEST] | 64.0% [TEST] |
| **M7** | Pipeline-Adjusted Mean | 0.6552 [TEST] | 31.48 [TEST] | 34.5% [TEST] | -1.90 [TEST] | 0.775 [TEST] | N/A |

### Granular Performance Slices for Deployed Model (B2):

#### 1. By Product ($n=25$ Sundays):
- **Widget Model X (Product 201):** MAE = 21.61 units [TEST], WAPE = 0.7922 [TEST] (Accuracy = 20.8% [TEST], Bias = -2.33 units [TEST]).
- **Widget Model Y (Product 202):** MAE = 14.83 units [TEST], WAPE = 0.7144 [TEST] (Accuracy = 28.6% [TEST], Bias = -0.09 units [TEST]).
- **Total Combined Demand:** MAE = 31.10 units [TEST], WAPE = 0.6474 [TEST] (Accuracy = 35.3% [TEST], Bias = -2.42 units [TEST]).
*Insight:* Portfolio aggregation reduces relative variance; total demand accuracy (35.3% [TEST]) substantially outperforms individual SKU forecasts (20.8% [TEST] and 28.6% [TEST]).

#### 2. Rolling Daily Test ($n=177$ Horizons):
Across all 177 daily walk-forward horizons in H2 2025:
- **MAE:** 30.62 units [TEST]
- **WAPE:** 0.6312 [TEST] (Accuracy: **36.9% [TEST]**)
- **Bias:** -2.67 units [TEST]

#### 3. Monthly Accuracy Slices (Sundays):
- **July ($n=4$):** WAPE 0.6181 [TEST] (Accuracy 38.2% [TEST], Bias +18.25u [TEST])
- **August ($n=5$):** WAPE 0.4138 [TEST] (Accuracy **58.6% [TEST]**, Bias -8.80u [TEST])
- **September ($n=4$):** WAPE 0.7614 [TEST] (Accuracy 23.9% [TEST], Bias -9.56u [TEST])
- **October ($n=4$):** WAPE 0.8913 [TEST] (Accuracy 10.9% [TEST], Bias +12.75u [TEST])
- **November ($n=5$):** WAPE 0.6376 [TEST] (Accuracy 36.2% [TEST], Bias -7.70u [TEST])
- **December ($n=3$):** WAPE 0.5877 [TEST] (Accuracy 41.2% [TEST], Bias -21.25u [TEST])

---

## 5. Theoretical Irreducible Noise Floor (Aleatoric Variance)

A critical scientific question in demand forecasting is: *How good could any model possibly be on this data?*

To answer this, we conducted an independent Monte Carlo audit (`stage10/audit/noise_floor.py`) simulating 100,000 weeks directly from the true underlying data generation process:
- Discrete Bernoulli order arrival ($p=0.42$ per weekday).
- Uniform random customer sampling ($\mathcal{U}[1, 3]$ customers per order).
- Known customer factors ($[1.2, 0.85, 1.35, 1.0, 0.7]$) and weekday multipliers.

### Noise Floor Findings:
- **Mean Weekly Demand:** 49.87 units [ORACLE]
- **Weekly Variance (Aleatoric):** 979.01 units$^2$ [ORACLE] ($\sigma = 31.29$ units [ORACLE])
- **Oracle Theoretical Minimum MAE:** 25.11 units [ORACLE]
- **Oracle Theoretical Minimum WAPE:** **0.5034 [ORACLE]** (Oracle Accuracy: **49.7% [ORACLE]**)

### Empirical Source of 68.2% Zero-Order Days:
The 68.2% zero-order day figure is mathematically sourced from the following database query executed against the 2025 production sales ledger:
```sql
SELECT 
    COUNT(DISTINCT order_date) as active_order_days,
    365 - COUNT(DISTINCT order_date) as zero_order_days,
    ROUND((365 - COUNT(DISTINCT order_date)) * 100.0 / 365, 3) as zero_order_day_pct
FROM sales_orders
WHERE order_date BETWEEN '2025-01-01' AND '2025-12-31';
```
**Query Execution Result:**
- Active order days: 116
- Zero-order days: 249 (out of 365 calendar days)
- Zero-order day %: **68.219%** ($249 / 365 = 68.2\%$)

### Scientific Conclusion on Model Performance:
Because daily order arrivals are governed by discrete probabilistic draws, **an omniscient Oracle possessing the exact simulation code and true parameters cannot achieve a WAPE lower than 0.5034 [ORACLE] (or accuracy above 49.7% [ORACLE])**. In plain English:
- **Deployed Model Selection:** The deployed model is a trailing 28-day mean because it achieved the lowest cross-validation WAPE (0.55 [CV] / 45.5% [CV] accuracy) during walk-forward validation inside the H1 2025 training window.
- **Machine Learning Benchmark:** Negative binomial count regression and gradient boosting did not beat the trailing 28-day mean on this one-year simulated dataset due to high demand intermittency (68.2% zero-order days).
- **Oracle Ceiling vs Deployed Model:** The theoretical oracle irreducible aleatoric error ceiling is WAPE 0.50 [ORACLE] (accuracy 50% [ORACLE]) vs the deployed model WAPE 0.65 [TEST] (accuracy 35.3% [TEST]; excess error over Oracle is only 0.14 WAPE).
- **Prediction Interval:** The prediction range is wide because discrete order arrivals are inherently stochastic.

---

## 6. System Integration & Guardrails

The weekly forecast is fully integrated across the SAGE operational surfaces:
1. **Today Executive Dashboard:** A dedicated "Next 7 days: expected new orders" forward-look card directly below the summary paragraph and above the operational alerts, displaying projected demand, committed scheduled orders, 12-week historical trend sparkline, and direct links to the deep-dive benchmark.
2. **Insights & Retrospective View:** Comprehensive "Weekly Order Forward-Look & Model Benchmark" (`#forecast`) containing interactive model comparisons, noise floor explanation, and the 25-week walk-forward audit log.
3. **Daily Executive Email & 1-Page PDF:** Standardized 1-line operational forward-look summary ensuring dispatch briefs remain strictly within the 1-page A4 print budget.
4. **Zero Look-Ahead & Idempotency:**
   - Stored walk-forward predictions for past days reflect strictly the data available as of that morning.
   - Future days are blocked with plain-English notices ("That day has not happened yet in this demo").
   - Dry-run operations strictly protect the delivery log from unauthorized SMTP transmissions.

---

## 7. Protocol Version 4 Addendum: Units Due ($D+1..D+7$) vs Units Placed ($D+1..D+7$)

As pre-registered in `stage10/prereg_forecast_v4.md` (committed at `4f003ca` prior to model evaluation), this addendum evaluates candidate models on the operational target:
$$y_{\text{due}}(D) = K(D) + S(D)$$
where $K(D)$ is **known booked units** already ordered in the ERP ledger on or before Day $D$ requested for delivery in $[D+1, D+7]$, and $S(D)$ is **short-notice units** ordered and requested within that same window.

### Benchmark Comparison Table: NEW Target ($y_{\text{due}}$) vs OLD Target ($y_{\text{placed}}$)

| Split & Horizon | Candidate Architecture | Target Definition | MAE (units) | WAPE | Accuracy ($1-\text{WAPE}$) | Bias (units) | 80% Coverage |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **CV ($n=21$ Sundays)** | Baseline 2: Trailing 28d Mean | OLD Target ($y_{\text{placed}}$) | 31.14 [CV] | 0.5455 [CV] | 45.5% [CV] | -1.88 [CV] | — |
| **CV ($n=21$ Sundays)** | Known Booked Only (No Model) | NEW Target ($y_{\text{due}}$) | 12.43 [CV] | 0.2258 [CV] | 77.4% [CV] | -12.43 [CV] | — |
| **CV ($n=21$ Sundays)** | **Booked + Trailing Short-Notice [DEPLOYED v4]** | **NEW Target ($y_{\text{due}}$)** | **10.99 [CV]** | **0.1996 [CV]** | **80.0% [CV]** | **-0.27 [CV]** | — |
| **TEST ($n=25$ Sundays)** | Baseline 2: Trailing 28d Mean | OLD Target ($y_{\text{placed}}$) | 31.10 [TEST] | 0.6474 [TEST] | 35.3% [TEST] | -2.42 [TEST] | — |
| **TEST ($n=25$ Sundays)** | Known Booked Only (No Model) | NEW Target ($y_{\text{due}}$) | 14.44 [TEST] | 0.3200 [TEST] | 68.0% [TEST] | -14.44 [TEST] | — |
| **TEST ($n=25$ Sundays)** | **Booked + Trailing Short-Notice [DEPLOYED v4]** | **NEW Target ($y_{\text{due}}$)** | **14.22 [TEST]** | **0.3152 [TEST]** | **68.5% [TEST]** | **-0.18 [TEST]** | **84.0% [TEST]** |
| **TEST ($n=177$ Daily)** | Baseline 2: Trailing 28d Mean | OLD Target ($y_{\text{placed}}$) | 30.62 [TEST] | 0.6312 [TEST] | 36.9% [TEST] | -2.67 [TEST] | — |
| **TEST ($n=177$ Daily)** | Known Booked Only (No Model) | NEW Target ($y_{\text{due}}$) | 10.93 [TEST] | 0.2381 [TEST] | 76.2% [TEST] | -10.93 [TEST] | — |
| **TEST ($n=177$ Daily)** | **Booked + Trailing Short-Notice [DEPLOYED v4]** | **NEW Target ($y_{\text{due}}$)** | **11.66 [TEST]** | **0.2540 [TEST]** | **74.6% [TEST]** | **-0.32 [TEST]** | **82.5% [TEST]** |

### Plain-English Attribution of Accuracy Gains:
Does accuracy rise from 35.3% / 36.9% to 68.5% / 74.6% because of a superior machine learning model?
**No. The accuracy gain stems directly from the known booked ledger commitments ($K(D)$).**
Because 68.0% to 76.2% of customer orders due in the next 7 days are already placed in advance (median lead time 6.0 days), they are known with 100% certainty on Day $D$. The predictive model is only responsible for estimating the residual 23.8% to 32.0% short-notice volume. Incorporating verified ERP commitments into the operational target eliminates aleatoric variance without claiming algorithmic superiority.

---

## 8. Model Artifact Details
- **Serialized Artifact:** `stage10/forecast/model.pkl` (and `stage10/forecast/outputs/model_v3.pkl`)
- **Artifact SHA256:** `a6b37c2e1558f1138a8e1165db602ec3ffc8de37a627fe01e6e37d1de427c6ab`
- **Output Audit Files:**
  - `stage10/forecast/outputs/test_weekly_forecasts.json` (walk-forward logs)
  - `stage10/forecast/outputs/metrics.json` (evaluation metrics)
  - `stage10/forecast/outputs/noise_floor.json` (aleatoric noise floor simulation)
