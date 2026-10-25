# SAGE Stage 10 — Next-Day Forecast & Seasonality Pre-Registration

> **Mandatory Scientific Framing:**
> *"SAGE performs controlled synthetic causal-attribution evaluation under an expert-defined causal model; it does not claim to prove real-world causality."*

**Pre-registration Timestamp:** 2026-10-25T07:15:00Z  
**Commit Status:** Committed prior to running any training or evaluation script.  
**Repository Branch:** `main`  

---

## 1. Objective & Scope

The SAGE Next-Day Operational Outlook provides plant managers and master schedulers with a forward-looking operational projection for day $t+1$, evaluated strictly as of day $t$ with zero look-ahead.

The system forecasts two complementary targets:
1. **Target 1 (T1) — "New Sales Tomorrow":** Unpredictable incoming order volume placed on day $t+1$.
2. **Target 2 (T2) — "Due Tomorrow":** Total order units requested for delivery on day $t+1$.

---

## 2. Target Variables & Order Book Lead-Lag Quantification

### Target 1 (T1): "New Sales Tomorrow"
- **Mathematical Definition:**
  $$T1_{t+1} = \sum_{i \in \text{SalesOrders},\; \text{order\_date} = t+1} \text{quantity\_ordered}_i$$
- **Information State at Day $t$:** Completely unknown on day $t$. Must be predicted using calendar seasonality, recent momentum, and operational state.

### Target 2 (T2): "Due Tomorrow"
- **Mathematical Definition:**
  $$T2_{t+1} = \sum_{i \in \text{SalesOrderLines},\; \text{req\_delivery\_date} = t+1,\; \text{order\_date} \le t} \max(0, \text{qty\_ordered}_i - \text{shipped}_i)$$
- **Information State at Day $t$:** Quantified from the existing sales order book.
- **Empirical Lead-Lag Analysis across 2025 (n = 230 sales orders):**
  - **Mean Lead Lag:** 6.12 days
  - **Median Lead Lag:** 6.00 days
  - **Min Lead Lag:** 3 days
  - **Max Lead Lag:** 10 days
  - **Orders with Lead Lag $\ge 1$ day:** **100.0%** (230 / 230)
  - **Orders with Lead Lag $\ge 3$ days:** **100.0%** (230 / 230)
  - **Same-Day / Next-Day Due Orders:** **0.0%** (0 / 230)
- **Conclusion:** By construction of the synthetic enterprise simulator, **100% of orders due on day $t+1$ are already recorded in the order book on day $t$**. Thus, $T2$ is known with high certainty from committed ERP tables, with small variations driven only by whether new orders could be accepted same-day (which simulator rules strictly bound to $\ge 3$ days advance notice).

---

## 3. Candidate Forecasting Models

For both T1 and T2, four candidate models are evaluated:

1. **Model (a) — Naive Lag-1:**
   $$\hat{y}_{t+1} = y_t$$
2. **Model (b) — Same-Weekday Last Week (Seasonal Baseline):**
   $$\hat{y}_{t+1} = y_{t-6}$$ (or $y_{t-7}$ for weekly cycle)
3. **Model (c) — 7-Day Rolling Mean:**
   $$\hat{y}_{t+1} = \frac{1}{7} \sum_{k=0}^{6} y_{t-k}$$
4. **Model (d) — HistGradientBoostingRegressor (GBDT with Quantile Loss):**
   - Implemented via `sklearn.ensemble.HistGradientBoostingRegressor`.
   - Three independent quantile estimators fit for an **80% prediction interval**:
     - $\text{Lower Bound (p10)}: \text{loss} = \text{"quantile"}, \text{quantile} = 0.10$
     - $\text{Point Forecast (p50)}: \text{loss} = \text{"quantile"}, \text{quantile} = 0.50$
     - $\text{Upper Bound (p90)}: \text{loss} = \text{"quantile"}, \text{quantile} = 0.90$
   - **Feature Vector (18 features, zero look-ahead $\le t$):**
     1. `weekday_0` ... `weekday_6`: Day-of-week one-hot encoding (Monday = 0, Sunday = 6).
     2. `day_of_month`: Day of month (1 to 31).
     3. `month`: Month of year (1 to 12).
     4. `lag_1`: Target value on day $t$.
     5. `lag_2`: Target value on day $t-1$.
     6. `lag_7`: Target value on day $t-6$.
     7. `rolling_7_mean`: Trailing 7-day mean of target.
     8. `rolling_7_std`: Trailing 7-day standard deviation of target.
     9. `open_customer_backlog`: Cumulative unfulfilled overdue units at day $t$.
     10. `units_due_tomorrow_on_books`: Exact units already scheduled for delivery on $t+1$.
     11. `material_101_stock`: Steel stock (kg) at day $t$.
     12. `material_102_stock`: Plastic stock (kg) at day $t$.
     13. `material_103_stock`: Copper stock (kg) at day $t$.

---

## 4. Evaluation Protocol & Pre-Registered Criteria

### Dataset Split
- **Training Period:** 2025-01-01 to 2025-06-30 (181 calendar days, Jan–Jun 2025).
- **Test Period (Walk-Forward):** 2025-07-01 to 2025-12-31 (184 calendar days, Jul–Dec 2025).
- **Evaluation Mechanism:** Expanding-window walk-forward validation. At each step $t$ in the test period, models predict $t+1$ using only information $\le t$.

### Performance Metrics
1. **WAPE (Weighted Absolute Percentage Error):**
   $$\text{WAPE} = \frac{\sum_{t} |y_t - \hat{y}_t|}{\sum_t y_t}$$
2. **MAPE (Mean Absolute Percentage Error on Non-Zero Days):**
   $$\text{MAPE} = \frac{1}{|T_{y > 0}|} \sum_{t \in T_{y > 0}} \frac{|y_t - \hat{y}_t|}{y_t}$$
3. **Median Absolute Error (MedAE):**
   $$\text{MedAE} = \text{median}(|y_t - \hat{y}_t|)$$
4. **Bias (Mean Error):**
   $$\text{Bias} = \frac{1}{N} \sum_t (\hat{y}_t - y_t)$$
5. **Interval Coverage (80% Target Interval):**
   $$\text{Coverage} = \frac{1}{N} \sum_t \mathbb{I}(p10_t \le y_t \le p90_t)$$
6. **Relative Improvement over Baseline (b):**
   $$\text{RelImp} = \frac{\text{WAPE}_{(b)} - \text{WAPE}_{(d)}}{\text{WAPE}_{(b)}}$$

### Pre-Registered Success Criteria
- **Pass Threshold for Model (d):**
  1. $\text{RelImp} \ge 15.0\%$ lower WAPE compared to Model (b) on Target 1 (New Sales).
  2. Test interval coverage within $70.0\% \le \text{Coverage} \le 90.0\%$ for an nominal 80% interval.
- **Pre-Registered Fallback:**
  If Model (d) fails either criterion, the deployed point forecast reverts to Model (b) (same-weekday last week) and the prediction interval reverts to empirical 7-day residual quantiles. Both models and metrics will be published transparently regardless of outcome.

---

## 5. Shortage Risk Classification Rule (Pre-Registered)

For each finished product ($p \in \{201, 202\}$) and total plant inventory, tomorrow's shortage risk is evaluated deterministically as of day $t$:

$$\text{Projected Ending Buffer}_{t+1} = \text{FG\_Stock}_t + \text{Planned\_Production}_{t+1} - \widehat{T2}_{t+1}$$

### Decision Rules:
- **HIGH RISK:** $\text{Projected Ending Buffer}_{t+1} < 0$ (Stockout imminent; orders will breach delivery commitment).
- **MEDIUM RISK:** $0 \le \text{Projected Ending Buffer}_{t+1} < \text{Safety\_Stock}_p$ (Buffer depleted below safety threshold).
- **LOW RISK:** $\text{Projected Ending Buffer}_{t+1} \ge \text{Safety\_Stock}_p$ (Operations comfortably cushioned).

### Evaluation on 2025 History:
Precision and Recall of HIGH / MEDIUM alerts will be measured against whether actual customer delivery backorders occurred on day $t+1$.

---

## 6. Deployed Production Model & Cryptographic Freezing

- Once evaluated, Model (d) is retrained on the complete 365 days of 2025.
- The model artifacts are serialized to `stage10/forecast/model.pkl`.
- The SHA256 cryptographic digest of `model.pkl` is recorded below in this file.
- The frozen model is then evaluated on the 10 demo days (2026-01-01 to 2026-01-10) with **zero retraining and zero weight adjustment**.

```
[MODEL_DIGEST_PLACEHOLDER]
```

---

## 7. Seasonality & Operational Lag Checks (Phase 4 Protocol)

### 1. False-Alarm Audit
- **2025 Baseline Audit:** Measure alert frequency outside the 10 injected incident disruption windows.
- **2026 Demo Feed Audit:** Evaluate alert behavior on scripted control days (Day 4 and Day 9) where no new operational disruption was introduced.
- **Output:** Categorical false-alarm rate across Critical, Needs Attention, and Watch tiers.

### 2. Seasonality Stress Test (Isolated Copy)
- **Isolation Guarantee:** Executed in an isolated in-memory copy of `analytics/daily_panel_baseline.parquet`. Real ERP and baseline files are untouched.
- **Stress Multipliers:**
  - $+40\%$ customer demand volume ramp applied across Q4 (Oct 1 to Dec 31).
  - $+25\%$ Friday spike applied across all Fridays.
- **Evaluation:** Re-run `priorities.py` and `trace.py`. Verify whether SAGE maintains causal integrity or falsely misattributes seasonal demand spikes to phantom supplier delays or machine breakdowns.

### 3. Physical Response Lag Analysis
- Compute propagation time across all 10 synthetic incidents:
  - **Lag A:** Time (days) from supplier delivery delay to raw material safety stock breach.
  - **Lag B:** Time (days) from raw material stockout to customer backlog creation.
- Report Min, Median, and Max lag days. Compare findings against SAGE's 7-day causal trace window.
