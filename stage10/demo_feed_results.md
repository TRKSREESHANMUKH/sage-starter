# SAGE 10-Day Scripted Demo Feed Evaluation Results

> **Overall Summary:** 8 Hits, 2 Partials, 0 Misses (100% Evaluation Coverage)

| Day | Date | Scenario Description | Actual Status | Top Alert Headline | Top Focus Action | Decision |
| :--- | :--- | :--- | :--- | :--- | :--- | :---: |
| Day 1 | 2026-01-01 | None | NORMAL | None | Routine operational shift review | **HIT** |
| Day 2 | 2026-01-02 | Elevated demand intake (28 units) → Warehouse finished goods buffer absorbs volume | WATCH | Elevated demand intake (Widget Model X surge of 28 units) | None | **HIT** |
| Day 3 | 2026-01-03 | Elevated demand intake (10 units) → Warehouse finished goods buffer absorbs volume | WATCH | Elevated demand intake (Widget Model X surge of 10 units) | None | **PARTIAL** |
| Day 4 | 2026-01-04 | EastCoast Components delivery (1d overdue) → Steel Rod 10mm buffer drawing down (90 kg) → Downstream impact: 5 customer orders overdue (54 units backlog). | NEEDS_ATTENTION | Overdue delivery from EastCoast Components (PO #19) | None | **HIT** |
| Day 5 | 2026-01-05 | EastCoast Components delivery (2d overdue) → Steel Rod 10mm buffer drawing down (63 kg) → Downstream impact: 7 customer orders overdue (77 units backlog). | NEEDS_ATTENTION | Overdue delivery from EastCoast Components (PO #19) | None | **HIT** |
| Day 6 | 2026-01-06 | Supplier delivery delay → Steel Rod 10mm stock depleted to 0 kg → Assembly line halted | CRITICAL | Raw material stockout on Steel Rod 10mm (0 kg in stock) | None | **HIT** |
| Day 7 | 2026-01-07 | Supplier delivery delay → Steel Rod 10mm stock depleted to 0 kg → Assembly line halted | CRITICAL | Raw material stockout on Steel Rod 10mm (0 kg in stock) | None | **HIT** |
| Day 8 | 2026-01-08 | Supplier partial delivery (40% fill rate) → Tracking material receipt shortfall | NEEDS_ATTENTION | Partial delivery from Global Polymers Co (PO #26) | None | **HIT** |
| Day 9 | 2026-01-09 | Inbound replenishment arrived → Assembly resumed → Oldest customer backorders shipping (FIFO) | NEEDS_ATTENTION | Standing customer backlog clearing (9 orders, 109 units) | None | **PARTIAL** |
| Day 10 | 2026-01-10 | Workcenter capacity constraint → Widget Model Y assembly shortfall of 1 units | NEEDS_ATTENTION | Production below plan (Widget Model Y shortfall of 1 units) | None | **HIT** |
