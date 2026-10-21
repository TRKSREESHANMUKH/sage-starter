# Pre-Registration Document: SAGE Real-World Generalisation Evaluation (Stage 10)

**Date**: 2026-10-11  
**Status**: PRE-REGISTERED (Prior to Test A Execution)  
**Governing Rule**: All seeds, scenario variations, targets, and decision thresholds are statically registered in this document prior to running simulations and attributions. Zero post-hoc threshold tuning or parameter adjustments permitted.

---

## 1. Test A: Fresh Synthetic Worlds (Out-of-Distribution Seeds)

### A. Seeds & Scenarios
- **Seeds**: `Seed 7` and `Seed 11` (unseen by prior training, parameter fitting, or calibration).
- **10 Core Operational Scenarios**: Evaluated with ±30% variation in magnitude and independent pseudo-random window start dates:
  1. `INC_01`: Single supplier delay (Supplier 1, lead-time shift: +30%).
  2. `INC_02`: Negative control (Zero operational disruption).
  3. `INC_03`: Customer demand surge (+30% demand volume, Product 201).
  4. `INC_04`: Assembly line throughput disruption (-30% capacity, Product 201).
  5. `INC_05`: Dual supplier delay (Suppliers 1 & 2 overlapping delay).
  6. `INC_06`: Compound supply delay & capacity shortfall (Supplier 2 + Product 202).
  7. `INC_07`: Zero-fill receipt disruption (Supplier 5).
  8. `INC_08`: Safety stock buffer absorption (Supplier 4 delay absorbed by safety stock).
  9. `INC_09`: Persistent stockout persistence (Extended Supplier 4 delay).
  10. `INC_10`: Seasonal demand variation control.

### B. Frozen Model & Decision Rules (Zero Refitting)
- **Causal Model**: Frozen Stage 7 GCM graph and fitted functional mechanisms (`stage7/fitted_causal_model.pkl`).
- **Empirical Null Thresholds (Frozen from Stage 7)**:
  - Method 1 (Peak Anomaly Attribution) $S_{p95} = 0.218006$
  - Method 2 (Distributional Change Attribution) $S_{p95} = 0.922611$
- **Target Node Mapping (Pre-registered Single Target per Scenario)**:
  - `INC_01`: `material_101_stock`
  - `INC_02`: `product_201_actual_production`
  - `INC_03`: `product_201_fg_stock`
  - `INC_04`: `product_201_actual_production`
  - `INC_05`: `material_101_stock`
  - `INC_06`: `product_202_actual_production`
  - `INC_07`: `material_103_stock`
  - `INC_08`: `material_103_stock`
  - `INC_09`: `material_101_stock`
  - `INC_10`: `product_201_demand_units`
- **Detection Definition**: An incident is classified as `DETECTED` if the true ground-truth driver clears the frozen Method 1 threshold ($|S| > 0.218006$) and ranks in the Top 3 exogenous drivers.
- **False Alarm Protocol**: 20 randomly sampled 14-day non-overlapping quiet windows from the baseline panel of each seed are scored against the same targets. Any window where an exogenous driver clears $S_{p95}$ without an operational incident is classified as a False Alarm.

---

## 2. Test B: Public Demand Dataset (Plausibility Check)
- **Dataset**: Classic daily store retail demand dataset (Kaggle/M5 Store Item Demand).
- **Split**: 70% historical calibration / 30% evaluation window containing real-world calendar disruptions (Thanksgiving, Black Friday, Christmas, documented promotions).
- **Hypothesis**: The calendar-to-demand causal mechanism flags known real-world surge events above baseline null threshold.

---

## 3. Test C: Real Company Ingest Adapter
- **Adapter**: `stage10/ingest_adapter.py` mapping raw enterprise CSV exports (orders, inventory, POs, workcenters) to the 29-column daily panel.
- **Specification**: Complete readiness rubric and boundary limitations documented in `stage10/DATA_READINESS.md`.
