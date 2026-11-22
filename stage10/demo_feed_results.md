# SAGE 10-Day Scripted Demo Feed Evaluation Results

> **Overall Summary:** 9 Hits, 1 Partials, 0 Misses (100% Evaluation Coverage)

| Day | Date | Scenario Description | Actual Status | Top Alert Headline | Top Focus Action | Decision |
| :--- | :--- | :--- | :--- | :--- | :--- | :---: |
| Day 1 | 2026-01-01 | Elevated demand intake (15 units) → Warehouse finished goods buffer absorbs volume | WATCH | Elevated demand intake (Widget Model X surge of 15 units) | Verify inbound purchase order arrivals scheduled for today | **PARTIAL** |
| Day 2 | 2026-01-02 | Elevated demand intake (36 units) → Warehouse finished goods buffer absorbs volume | WATCH | Elevated demand intake (Widget Model X surge of 36 units) | Verify inbound purchase order arrivals scheduled for today | **HIT** |
| Day 3 | 2026-01-03 | EastCoast Components delivery (1d overdue) → Steel Rod 10mm buffer drawing down (120 kg) → Downstream impact: 2 customer orders overdue (21 units backlog). | NEEDS_ATTENTION | Overdue delivery from EastCoast Components (PO #19) | Expedite PO #19 with EastCoast Components | **HIT** |
| Day 4 | 2026-01-04 | EastCoast Components delivery (2d overdue) → Steel Rod 10mm buffer drawing down (90 kg) → Downstream impact: 2 customer orders overdue (21 units backlog). | NEEDS_ATTENTION | Overdue delivery from EastCoast Components (PO #19) | Expedite PO #19 with EastCoast Components | **HIT** |
| Day 5 | 2026-01-05 | EastCoast Components delivery (3d overdue) → Steel Rod 10mm buffer drawing down (63 kg) → Downstream impact: 4 customer orders overdue (44 units backlog). | NEEDS_ATTENTION | Overdue delivery from EastCoast Components (PO #19) | Expedite PO #19 with EastCoast Components | **HIT** |
| Day 6 | 2026-01-06 | EastCoast Components delivery (4d overdue) → Steel Rod 10mm buffer drawing down (50 kg) → Downstream impact: 6 customer orders overdue (66 units backlog). | CRITICAL | Steel Rod 10mm at safety stock (50 kg remaining) — EastCoast Components PO #19 overdue | Expedite PO #19 with EastCoast Components | **HIT** |
| Day 7 | 2026-01-07 | Supplier delivery delay → Steel Rod 10mm stock depleted to 0 kg → Assembly line halted | CRITICAL | Raw material stockout on Steel Rod 10mm (0 kg in stock) | Expedite PO #19 with EastCoast Components | **HIT** |
| Day 8 | 2026-01-08 | Supplier partial delivery (40% fill rate) → Tracking material receipt shortfall | NEEDS_ATTENTION | Partial delivery from Global Polymers Co (PO #20) | Track balance shipment from Global Polymers Co (PO #20) | **HIT** |
| Day 9 | 2026-01-09 | None | NORMAL | None | Verify inbound purchase order arrivals scheduled for today | **HIT** |
| Day 10 | 2026-01-10 | Supplier partial delivery (60% fill rate) → Tracking material receipt shortfall | NEEDS_ATTENTION | Partial delivery from Global Polymers Co (PO #22) | Inspect assembly tooling on Widget Model Y | **HIT** |
