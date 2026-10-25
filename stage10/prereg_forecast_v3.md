# SAGE — Pre-Registration: Weekly Order Forecast Protocol (Version 3)

> **Mandatory Research Framing:**  
> *"SAGE performs controlled synthetic causal-attribution evaluation under an expert-defined causal model; it does not claim to prove real-world causality."*

**Pre-registration Timestamp:** 2026-10-25T17:30:00Z  
**Commit Status:** Pre-registered and committed prior to model selection and test evaluation.

---

## 1. Problem Formulation & Targets

The goal is to provide an operational forward-look over a weekly planning horizon (7 days) for plant operations, replacing short-horizon next-day forecasts with operational weekly capacity planning.

For any given forecast origin date $D$:
1. **Target 1 ("New Orders Expected, Next 7 Days"):** Total units of NEW customer orders placed on days $D+1$ through $D+7$ inclusive ($t \in [D+1, D+7]$), defined as sales orders with `order_date` $\in [D+1, D+7]$, excluding cancelled orders. Evaluated separately for Product 201 (Widget Model X), Product 202 (Widget Model Y), and Total.
2. **Target 2 ("Already Due in Next 7 Days — Known Facts"):** Total units of customer orders already placed on or before origin date $D$ (`order_date` $\le D$, excluding cancelled) with `requested_delivery_date` $\in [D+1, D+7]$. This is an exact known order book fact, not a statistical forecast.

---

## 2. Empirical Evidence Behind Assumptions

Pre-flight operational audit across historical 2025 ERP transactions ($n=221$ sales orders):
1. **Demand Metric Definition (a):** Units on sales orders by `order_date` match daily panel demand units outside synthetic disruption windows. "New orders" is strictly operationalized as customer order placements with `order_date` in the 7-day window.
2. **Order Lead Time (b):** Customer order advance notice has a minimum of 3 days and a median of 6.00 days (mean 6.12 days; Product 201: min 3d, median 6.0d; Product 202: min 3d, median 6.0d). 100% of orders are placed at least 3 days in advance.
3. **Intermittent Demand & Zero-Order Days (c):** Daily customer demand is highly intermittent across 365 calendar days in 2025:
   - Product 201: 281 zero-order days (77.0% zero days, 84 active order days).
   - Product 202: 286 zero-order days (78.4% zero days, 79 active order days).
   - Total (combined): 249 zero-order days (68.2% zero days, 116 active order days).
4. **Implication for Forecast Resolution:** Daily point forecasting on 68.2% zero days yields high variance and uninformative daily WAPE > 1.0 (as observed in earlier daily Model d WAPE 1.1055). Aggregating daily predictions to a weekly 7-day block ($D+1..D+7$) smooths intermittency while aligning directly with weekly production shift scheduling.

---

## 3. Data Split Protocol & Temporal Isolation

Strict temporal quarantine is enforced at every origin date $D$: features and models use **only** information available on or before day $D$.

- **Training Period:** 2025-01-01 to 2025-06-30 (H1 2025, 181 calendar days).
- **Model & Hyperparameter Selection:** Conducted strictly **inside** the training window (Jan–Jun 2025) using 4-fold expanding-window time-series cross-validation. No test data is seen during model or parameter selection.
- **Out-of-Sample Test Period:** 2025-07-01 to 2025-12-31 (H2 2025, 184 calendar days), walk-forward evaluation with monthly refitting at the end of each calendar month.
- **Reporting Cohorts:**
  - All rolling daily origins ($n=184$ overlapping 7-day test windows, overlap noted).
  - Non-overlapping Sunday origins ($n=26$ distinct weekly horizons).
- **Scripted Demo Days (2026-01-01 to 2026-01-10):** Evaluated strictly as an out-of-sample operational walkthrough; demo days are scripted and must not be conflated with generalization accuracy.

---

## 4. Candidate Models

### Baselines
1. **Model (1) — Last 7 Days Total:** Sum of actual order units in the trailing 7 days $[D-6, D]$.
2. **Model (2) — Trailing 28-day Mean $\times$ 7:** Trailing 4-week average daily rate multiplied by 7.
3. **Model (3) — Weekday $\times$ Month Empirical Mean:** Summed empirical mean order volume by day of week and calendar month.
4. **Model (4) — Zero Forecast:** Predicting 0 units for the next 7 days.

### Machine Learning & Statistical Models
5. **Model (5) — Negative Binomial GLM:** Daily count regression with log link function on calendar features (day of week, month, week of year) and autoregressive lags ($t-1, t-7, t-14, t-28$). Daily predictions are summed across $D+1..D+7$.
6. **Model (6) — Gradient Boosted Decision Trees (HistGradientBoosting / LightGBM):** Trained on daily order units with calendar features (day of week, day of month, month, week of year), autoregressive demand lags ($1, 7, 14, 28$), and rolling demand means ($7, 28$). Daily point forecasts are summed to the 7-day total. Prediction intervals (80% CI) are computed via Quantile Regression (quantile loss at $\alpha=0.10$ and $\alpha=0.90$) or split-conformal residuals from walk-forward validation.
7. **Model (7) — Best Model with Known-Orders Adjustment:** If customer order pipeline or advance booking signals improve validation WAPE, an additive pipeline adjustment is applied.

### Deployed Model Selection Rule
The deployed model is chosen strictly by the **lowest weekly WAPE on time-series cross-validation within the Jan–Jun 2025 training set**. All models are reported on the test set, regardless of which model performs best on test.

---

## 5. Evaluation Metrics

For each model, evaluated per product (201, 202) and Total:
- **MAE:** Mean Absolute Error in units: $\frac{1}{N}\sum |y_i - \hat{y}_i|$.
- **WAPE:** Weighted Absolute Percentage Error: $\frac{\sum |y_i - \hat{y}_i|}{\sum y_i}$.
- **Accuracy %:** Defined as $1 - \text{WAPE}$, reported **only** when $\text{WAPE} < 1.0$. If $\text{WAPE} \ge 1.0$, reported plainly as "No better than predicting zero".
- **MAPE (Zero-guarded):** $\frac{1}{N}\sum \frac{|y_i - \hat{y}_i|}{\max(y_i, 1)}$.
- **Bias:** Mean error: $\frac{1}{N}\sum (\hat{y}_i - y_i)$.
- **MASE:** Mean Absolute Scaled Error relative to Baseline Model (1).
- **80% Prediction Interval Coverage:** Percentage of test actuals falling within $[\hat{y}_{10}, \hat{y}_{90}]$.
- **Average Interval Width:** Mean $(\hat{y}_{90} - \hat{y}_{10})$.
- **Slices:** Breakdown by weekday of origin, calendar month, and synthetic seasonal disruption windows (INC_03 demand spike, INC_10 year-end ramp).

---

## 6. Noise Floor Analysis

To separate model error from irreducible aleatoric randomness, an audit script reads simulator parameters (base demand Poisson/Normal rates, seasonal multipliers, weekday factors) to compute the theoretical expected weekly demand $E[Y_t]$.
The variance $\text{Var}(Y_t)$ around the theoretical expectation represents the irreducible noise floor. The gap between the deployed model's test error and the noise floor is reported in plain English.
