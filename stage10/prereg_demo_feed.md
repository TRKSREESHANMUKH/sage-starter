# SAGE — Stage 10 Pre-Registration: Ten-Day Scripted Demo Feed Protocol (1–10 January 2026)

> **Mandatory Framing Statement:**
> "SAGE performs controlled synthetic causal-attribution evaluation under an expert-defined causal model; it does not claim to prove real-world causality."

---

## 1. Protocol Locking & Pre-Registration Notice
This document pre-registers the exact evaluation criteria, expected causal narratives, alert tiers, root cause chains, and hit/partial/miss decision rules for the 10-day operational demonstration feed (2026-01-01 to 2026-01-10).

This document is committed and locked BEFORE the feed generator script executes or ingests any new day pack into the SAGE live database.

---

## 2. Opening Position Baseline (as of 2025-12-31)
Following the year-end state gate audit:
- Stale customer orders (>60 days overdue) and overdue PO #18 are cancelled on 2025-12-31 (recorded as cancellations, not deletions).
- Stock counts are adjusted to normal operating levels (materials above reorder point: Steel Rod 500 kg, Plastic 300 kg, Copper 250 m; finished goods: Widget X 45 units, Widget Y 35 units).
- Three seed purchase orders placed in December 2025:
  1. PO #19 (Supplier 4, Steel Rod 400 kg, ordered 2025-12-25, expected 2026-01-03)
  2. PO #20 (Supplier 3, Plastic Granules 250 kg, ordered 2025-12-21, expected 2026-01-04)
  3. PO #21 (Supplier 5, Copper Wire 200 m, ordered 2025-12-25, expected 2026-01-06)

---

## 3. Ten-Day Pre-Registered Predictions & Decision Rules

| Day | Date | Scenario Description | Expected Banner | Expected Alert & Tier | Expected Cause Chain | Top Focus Item |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Day 1** | 2026-01-01 | Normal operations: routine orders, production, shipping | All normal | No alerts (Normal) | None (Routine operations) | Routine production monitoring |
| **Day 2** | 2026-01-02 | Demand spike on Widget Model X (~2.5x normal), stock covers | Watch / Attention | Elevated demand alert (Watch) | Demand surge absorbed by buffer stock | Monitor finished goods depletion |
| **Day 3** | 2026-01-03 | Steel delivery (Supplier 4, PO #19) does not arrive; stock above safety | Watch | Supplier delay watch (Watch) | Inbound PO delay, buffer intact | Expedite delivery with Supplier 4 |
| **Day 4** | 2026-01-04 | Plastic granules (Supplier 3) arrives 60% partial; steel 1d overdue | Needs Attention | Partial delivery + steel delay (Needs Attention) | Partial receipt + ongoing supplier delay | Track plastic balance & steel delay |
| **Day 5** | 2026-01-05 | Capacity disruption: line downtime, Widget Model Y -50% | Needs Attention | Production below plan (Needs Attention) | Equipment/capacity bottleneck | Investigate line downtime |
| **Day 6** | 2026-01-06 | Steel 3d overdue, demand high, steel at safety, production short, 1st late SO | Critical | Compound disruption (Critical) | Supplier 4 delay -> steel at safety -> production cut -> customer delay | Expedite steel; prioritize customer orders |
| **Day 7** | 2026-01-07 | Steel stockout (0 kg), Widget Model X halted, overdue orders grow | Critical | Severe stockout & backlog (Critical) | Stockout -> line halt -> escalating backlog | Expedite delivery; customer priority list |
| **Day 8** | 2026-01-08 | Steel arrives 5d late; production resumes; plastic balance arrives | Improving | Recovery in progress (Needs Attention) | Inbound arrival -> production resume -> backlog clearing | Accelerate production to clear backlog |
| **Day 9** | 2026-01-09 | Friday demand peak matches weekly seasonal pattern (control) | Improving / Calm | Normal seasonal peak (Watch/Normal) | Backlog clearance continuing; no false alarm | Maintain shipping throughput |
| **Day 10** | 2026-01-10 | Dual unrelated minor issues: Widget Y -20% and late plastic reorder | Needs Attention | Dual separate alerts (Needs Attention) | Two distinct unmerged issues | Line throughput check & vendor follow-up |

---

## 4. Objective Scoring Criteria (Hit / Partial / Miss)

For each day, the evaluation score is determined by three deterministic components:
1. **Tier Match (40%)**: Did the banner severity match the expected tier (e.g. Critical on Day 6 & 7; Calm/Normal on Day 1; Needs Attention on Day 4, 5, 8, 10)?
2. **Entity / Issue Attribution (40%)**: Did the alert identify the correct operational entity and symptom (e.g. Supplier 4 / Steel on Days 3, 6, 7; Supplier 3 on Day 4; Widget Model Y capacity on Day 5)?
3. **Action / Focus Match (20%)**: Does the top focus item reflect the primary operational bottleneck?

**Evaluation Outcome Definitions:**
- **HIT**: Meets all 3 components (Tier, Entity, and Action).
- **PARTIAL**: Meets at least 2 components (e.g. correct entity and action, but tier differed by one step like Watch vs Needs Attention).
- **MISS**: Misses primary entity/root driver or produces false alarm on calm day / control.
