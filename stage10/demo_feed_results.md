# SAGE 10-Day Scripted Demo Feed Evaluation Results

> **Overall Summary:** 10 Hits, 0 Partials, 0 Misses (100% Evaluation Coverage)

| Day | Date | Scenario Description | Actual Status | Top Alert Headline | Top Focus Action | Decision |
| :--- | :--- | :--- | :--- | :--- | :--- | :---: |
| Day 1 | 2026-01-01 | None | NORMAL | None | Verify inbound purchase order arrivals scheduled for today | **HIT** |
| Day 2 | 2026-01-02 | Elevated demand intake (36 units) → Warehouse finished goods buffer absorbs volume | WATCH | Elevated demand intake (Widget Model X surge of 36 units) | Verify inbound purchase order arrivals scheduled for today | **HIT** |
| Day 3 | 2026-01-03 | EastCoast Components delivery (1d overdue) → Steel Rod 10mm buffer drawing down (120 kg) → Downstream impact: 4 customer orders overdue (42 units backlog). | NEEDS_ATTENTION | Overdue delivery from EastCoast Components (PO #19) | Expedite PO #19 with EastCoast Components | **HIT** |
| Day 4 | 2026-01-04 | EastCoast Components delivery (2d overdue) → Steel Rod 10mm buffer drawing down (90 kg) → Downstream impact: 5 customer orders overdue (54 units backlog). | NEEDS_ATTENTION | Overdue delivery from EastCoast Components (PO #19) | Expedite PO #19 with EastCoast Components | **HIT** |
| Day 5 | 2026-01-05 | EastCoast Components delivery (3d overdue) → Steel Rod 10mm buffer drawing down (63 kg) → Downstream impact: 7 customer orders overdue (77 units backlog). | NEEDS_ATTENTION | Overdue delivery from EastCoast Components (PO #19) | Expedite PO #19 with EastCoast Components | **HIT** |
| Day 6 | 2026-01-06 | EastCoast Components delivery (4d overdue) → Steel Rod 10mm buffer drawing down (50 kg) → Downstream impact: 9 customer orders overdue (99 units backlog). | CRITICAL | Steel Rod 10mm at safety stock (50 kg remaining) — EastCoast Components PO #19 overdue | Expedite PO #19 with EastCoast Components | **HIT** |
| Day 7 | 2026-01-07 | Supplier delivery delay → Steel Rod 10mm stock depleted to 0 kg → Assembly line halted | CRITICAL | Raw material stockout on Steel Rod 10mm (0 kg in stock) | Expedite PO #19 with EastCoast Components | **HIT** |
| Day 8 | 2026-01-08 | Supplier partial delivery (40% fill rate) → Tracking material receipt shortfall | NEEDS_ATTENTION | Partial delivery from Global Polymers Co (PO #20) | Track balance shipment from Global Polymers Co (PO #20) | **HIT** |
| Day 9 | 2026-01-09 | Inbound replenishment arrived → Assembly resumed → Oldest customer backorders shipping (FIFO) | NEEDS_ATTENTION | Standing customer backlog clearing (3 orders, 46 units) | Verify inbound purchase order arrivals scheduled for today | **HIT** |
| Day 10 | 2026-01-10 | Workcenter capacity constraint → Widget Model Y assembly shortfall of 5 units | NEEDS_ATTENTION | Production below plan (Widget Model Y shortfall of 5 units) | Inspect assembly tooling on Widget Model Y | **HIT** |
