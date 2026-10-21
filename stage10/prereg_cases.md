# SAGE — Stage 10 Pre-Registration: Ten Demo Cases Protocol

> **Framing Statement:**
> "SAGE performs controlled synthetic causal-attribution evaluation under an expert-defined causal model; it does not claim to prove real-world causality."

---

## 1. Scope & Objective
This pre-registration document establishes the deterministic evaluation protocol for the ten demonstration cases in SAGE Stage 9 Final 2. All evaluation rules, dates, ground-truth scenarios, and scoring criteria are locked prior to demonstration execution.

---

## 2. Pre-Registered Case Definitions

```
┌───────┬────────────┬─────────────┬──────────────────────────┬───────────────────────────┬──────────────────┐
│ Case  │ Date       │ Scenario ID │ Synthetic Event          │ Expected Root Driver      │ Expected Tier    │
├───────┼────────────┼─────────────┼──────────────────────────┼───────────────────────────┼──────────────────┤
│ C-01  │ 2025-03-31 │ INC_03      │ Customer Demand Spike    │ sales_demand_product_201  │ HIGH (Cleared)   │
│ C-02  │ 2025-10-02 │ INC_04      │ Capacity Disruption      │ production_capacity_prod1 │ HIGH (Cleared)   │
│ C-03  │ 2025-07-22 │ INC_06      │ Compound Bottleneck      │ supp_delay + line_fault   │ HIGH (Cleared)   │
│ C-04  │ 2025-08-07 │ INC_07      │ Partial Goods Receipt    │ po_fill_rate_deviation    │ MEDIUM (Warning) │
│ C-05  │ 2025-03-02 │ INC_08      │ Buffer Absorption        │ po_delay (buffer intact)  │ NOISE / ABSORBED │
│ C-06  │ 2025-08-20 │ INC_09      │ Delay Onset (PO #18)     │ supplier_4_po_delay       │ MEDIUM (Warning) │
│ C-07  │ 2025-10-20 │ INC_09      │ Delay Crisis (PO #18)    │ supplier_4_po_delay       │ HIGH (Cleared)   │
│ C-08  │ 2025-12-01 │ INC_10      │ Seasonal Demand Rise     │ seasonal_calendar_volume  │ NOISE (Control)  │
│ C-09  │ 2025-01-15 │ INC_02      │ Calm Day Baseline        │ normal_variation          │ NOISE (Control)  │
│ C-10  │ 2025-12-31 │ Standing    │ Cumulative Year-End      │ annual_standing_position  │ HIGH (Standing)  │
└───────┴────────────┴─────────────┴──────────────────────────┴───────────────────────────┴──────────────────┘
```

---

## 3. Two-Way Stage 7 Metric Reclassification

Following the audit of the Stage 4 supplier selection mechanism (where `choose_supplier` in `simulator/daily_simulation.py` reused the 2025-01-01 seed and never assigned POs to Suppliers 1 and 2), Stage 7 metrics are transparently reported in two views:

### View 1: All Ten Evaluation Scenarios (Raw Synthetic Suite)
- Scenarios Evaluated: 10 (6 real-cause, 2 controls, 2 inactive vendor delays INC_01 & INC_05)
- **Attribution Accuracy @ 1 (AC@1):** 33.3%
- **Attribution Accuracy @ 3 (AC@3):** 66.7%
- **Mean Reciprocal Rank (MRR):** 0.5620
- **False Positive Rate on Controls (FPR):** 0.0%
- **5-Seed Stability Pass Rate:** 90.0%

### View 2: Active Physical-Cause Scenarios (Audited Ground Truth)
- Scenarios Evaluated: 4 (INC_03, INC_04, INC_06, INC_08; excluding INC_01 & INC_05 which caused zero physical impact)
- **Attribution Accuracy @ 1 (AC@1):** 50.0%
- **Attribution Accuracy @ 3 (AC@3):** 100.0%
- **Mean Reciprocal Rank (MRR):** 0.7431
- **False Positive Rate on Controls (FPR):** 0.0%
- **5-Seed Stability Pass Rate:** 100.0%

---

## 4. Mechanical Classification Rules
1. **Controls (INC_02, INC_10):**
   - Correctly classified as non-disruptive if attribution score $\le 0.2180$ (95th-percentile baseline null threshold).
2. **Buffer Absorption (INC_08):**
   - Classified as `Buffer absorption confirmed` when supplier delay $> 0$ days but material stock $> \text{safety stock}$ throughout the evaluation window.
3. **Physical Disruptions (INC_03, INC_04, INC_06, INC_09):**
   - Classified as `Calibrated detection` when top-ranked driver matches the ground-truth injection and attribution score $> 0.2180$.
