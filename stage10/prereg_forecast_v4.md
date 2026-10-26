# SAGE — Pre-Registration: Weekly Order Forecast Protocol (Version 4 Addendum)

> **Mandatory Research Framing:**  
> *"SAGE performs controlled synthetic causal-attribution evaluation under an expert-defined causal model; it does not claim to prove real-world causality."*

**Pre-registration Timestamp:** 2026-10-26T17:30:00Z  
**Commit Status:** Pre-registered and committed prior to training evaluation and reporting.

---

## 1. Scope & Purpose of Protocol v4
This Addendum protocol refines the Weekly Order Forecast specifications established in `stage10/prereg_forecast_v3.md`:
1. **Explicit Metric Tagging:** Every quantitative figure reported in `FORECAST_REPORT.md`, Method page, or documentation must carry an explicit scope qualifier:
   - `[CV]`: In-sample walk-forward cross-validation on H1 2025 ($n=21$ Sundays).
   - `[TEST]`: Strictly out-of-sample walk-forward test on H2 2025 ($n=25$ Sundays, $n=177$ daily horizons).
   - `[ORACLE]`: Theoretical aleatoric error ceiling derived from 100,000-week Monte Carlo simulation of the known data generator.
2. **Empirical Grounding of Demand Intermittency:** The 68.2% zero-order day figure is mathematically sourced from SQL query:
   ```sql
   SELECT 
       COUNT(DISTINCT order_date) as active_order_days,
       365 - COUNT(DISTINCT order_date) as zero_order_days,
       ROUND((365 - COUNT(DISTINCT order_date)) * 100.0 / 365, 3) as zero_order_day_pct
   FROM sales_orders
   WHERE order_date BETWEEN '2025-01-01' AND '2025-12-31';
   ```
   Yielding 116 active order days, 249 zero-order days (68.219% $\approx$ 68.2%).
3. **Plain-English Deployed Model Disclosure:**
   - The deployed production model is the **Trailing 28-day Mean $\times$ 7**.
   - It was chosen solely because it achieved the lowest cross-validation WAPE (0.5455 [CV] / 45.5% [CV] accuracy) during H1 2025 cross-validation.
   - Negative Binomial GLM (WAPE 0.5976 [CV]) and Quantile GBDT (WAPE 0.5889 [CV]) did not beat the trailing mean on this 1-year simulated dataset due to high intermittency (68.2% zero-order days).
   - The theoretical oracle error floor is WAPE 0.5034 [ORACLE] (accuracy ceiling 49.7% [ORACLE]), vs the deployed model's test WAPE 0.6474 [TEST] (accuracy 35.3% [TEST]).
   - The prediction range is wide because discrete customer demand arrivals are stochastic.
4. **Card UI & Slim Numbers Strip:**
   - The forecast card is positioned directly below the editorial summary paragraph and above the alert cards.
   - The "Shortage risk" badge is omitted from the card layout.
   - When viewing past days, the numbers strip remains compact/slimmed without uncomputed or future metrics.
