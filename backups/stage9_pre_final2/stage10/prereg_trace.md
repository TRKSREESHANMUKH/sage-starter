# Pre-Registration: Cause-Chain Trace Backtest (Stage 9 Part E5)

**Date Registered:** October 17, 2026  
**Status:** PRE-REGISTERED (Frozen prior to execution)  
**Framing Sentence:** SAGE performs controlled synthetic causal-attribution evaluation under an expert-defined causal model; it does not claim to prove real-world causality.

---

## 1. Objective & Hypothesis
This pre-registration defines the deterministic evaluation protocol for the SAGE Cause-Chain Trace (`stage9/trace.py`). The trace walks upstream through the frozen expert causal DAG from abnormal symptoms to candidate upstream drivers across a 7-day backward window with strict temporal order enforcement.

### Hypotheses:
1. **Scenario Hit Rate (Primary):** On the 10 frozen synthetic scenario panels (INC_01 through INC_10), the trace root will match the scenario's true exogenous driver in all detectable benchmark scenarios (INC_03 demand spike, INC_04 capacity disruption, INC_06 two-cause case).
2. **False Alarm Rate (Controls):** On the 365 days of the baseline panel (INC_01 / no incident), the number of days with detected false-alarm chains will be recorded. For negative control scenarios (INC_02 no-incident, INC_08 absorbed delay, INC_10 seasonal control), false detections will be reported honestly.
3. **Demo Extension (2026):** On the 10 fed days of January 2026, the trace will identify the Supplier 1 delay on Material 101 (appearing ~Jan 3) and the Product 201 demand spike (appearing ~Jan 6) as recorded in `business_events_demo`.

---

## 2. Fixed Pre-Registered Rules (Zero Post-Hoc Tuning)

### E1. Abnormal Detection Rule
- **Baseline Reference:** `analytics/daily_panel_baseline.parquet` (365 days, 2025-01-01 to 2025-12-31).
- **Per-Weekday Grouping:** Median ($M_w$) and Median Absolute Deviation ($\text{MAD}_w$) computed per weekday $w \in \{0, \dots, 6\}$.
- **Standard Continuous Nodes:** A value $x_t$ on weekday $w$ is abnormal if:
  $$\left| 0.6745 \times \frac{x_t - M_w}{\text{MAD}_w} \right| \ge 3.5$$
- **Zero-Inflated Nodes (where $\text{MAD}_w == 0$):**
  A value $x_t > 0$ is abnormal if $x_t > P_{99}(\text{baseline})$.

### E2. Upstream DAG Walk & Temporal Ordering
- **DAG Edges:** Identical to frozen Stage 7 NetworkX DAG (`stage7/build_causal_model.py`).
- **Symptom Nodes:**
  - Product due backlog: `product_201_due_backlog_units`, `product_202_due_backlog_units`
  - Production shortfall: `product_201_production_shortfall_units`, `product_202_production_shortfall_units`
  - Machine capacity shortfall: `product_201_capacity_shortfall_units`, `product_202_capacity_shortfall_units`
  - Raw material low stock: `material_101_stock`, `material_102_stock`, `material_103_stock` (stock $\le$ safety stock)
- **Temporal Order Constraint:** An upstream parent node $u$ at date $t_u$ can only cause downstream symptom $v$ at date $t_v$ if $t_u \le t_v$.
- **Window:** Up to 7 trailing calendar days ($t - 6 \le t_u \le t$).
- **Confidence Classification:**
  - `Seen end to end`: Every link in the chain from root to symptom is abnormal and strictly ordered in time.
  - `Partly seen`: At least one link in the chain was abnormal, but intermediate links are missing or contemporaneous.
  - `No upstream explanation found`: Symptom is abnormal, but no upstream parent was abnormal in the 7-day window.

---

## 3. Evaluation Protocol
1. **Frozen 10 Scenarios:**
   - Run trace across daily panels for INC_01 through INC_10.
   - Ground truth answer keys are read strictly by the research evaluation harness; `stage9/trace.py` never reads ground truth files.
   - Record: True driver, Identified root, First detection date, Confidence label.
2. **365 Baseline Days:**
   - Run trace on each date of `analytics/daily_panel_baseline.parquet`.
   - Count days with any abnormal chain (False-Alarm Days).
3. **10 Demo Days (2026-01-01 to 2026-01-10):**
   - Run trace sequentially on each fed day.
   - Compare identified root against `incidents_demo_2026.yaml` / `business_events_demo`.
4. **Honest Reporting:** All metrics (hits, misses, false alarm days) will be published directly in the Trust panel and documentation without alteration.
