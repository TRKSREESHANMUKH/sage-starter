# SAGE — Single Source of Demo Facts (Days 1–10)

> **Mandatory Scientific Framing:**  
> "SAGE performs controlled synthetic causal-attribution evaluation under an expert-defined causal model; it does not claim to prove real-world causality."

---

## 1. Daily Operations & Backlog Ledger (Days 1–10)

| Day | Date | Tier | Overdue (< D) | Due Today (== D) | Open Backlog (Total) | Opening Stock (Steel / Plast / Cu) | Top Alert Headline |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| Day 1 | 2026-01-01 | **NORMAL** | 0 ord (0u) | 0 ord (0u) | 0 ord (0u) | 215kg / 204kg / 184m | None |
| Day 2 | 2026-01-02 | **WATCH** | 0 ord (0u) | 6 ord (50u) | 6 ord (50u) | 185kg / 130kg / 105m | Elevated demand intake (Widget Model X surge of 28 units) |
| Day 3 | 2026-01-03 | **NEEDS_ATTENTION** | 4 ord (42u) | 4 ord (44u) | 8 ord (86u) | 150kg / 118kg / 99m | Overdue delivery from EastCoast Components (PO #19) |
| Day 4 | 2026-01-04 | **NEEDS_ATTENTION** | 5 ord (54u) | 4 ord (37u) | 9 ord (91u) | 120kg / 108kg / 94m | Overdue delivery from EastCoast Components (PO #19) |
| Day 5 | 2026-01-05 | **NEEDS_ATTENTION** | 7 ord (77u) | 3 ord (28u) | 10 ord (105u) | 90kg / 248kg / 89m | Overdue delivery from EastCoast Components (PO #19) |
| Day 6 | 2026-01-06 | **CRITICAL** | 8 ord (91u) | 3 ord (32u) | 11 ord (123u) | 63kg / 238kg / 85m | Steel Rod 10mm at safety stock (47 kg remaining) — EastCoast Components PO #19 overdue |
| Day 7 | 2026-01-07 | **CRITICAL** | 9 ord (109u) | 3 ord (18u) | 12 ord (127u) | 47kg / 232kg / 283m | Raw material stockout on Steel Rod 10mm (0 kg in stock) |
| Day 8 | 2026-01-08 | **NEEDS_ATTENTION** | 9 ord (109u) | 2 ord (14u) | 11 ord (123u) | 0kg / 232kg / 283m | Partial delivery from Global Polymers Co (PO #20) |
| Day 9 | 2026-01-09 | **NEEDS_ATTENTION** | 9 ord (109u) | 2 ord (12u) | 11 ord (121u) | 353kg / 316kg / 275m | Standing customer backlog (9 orders, 109 units) |
| Day 10 | 2026-01-10 | **NEEDS_ATTENTION** | 9 ord (109u) | 2 ord (10u) | 11 ord (119u) | 313kg / 302kg / 269m | Production below plan (Widget Model Y shortfall of 1 unit) |

---

## 2. Daily Forecast Strip Values & Realized Ledger Actuals (Days 1–10)

> *Method Note*: The demo feed's order rate is about 3x the 2025 rate, so demo-day forecasts are not an accuracy test. Accuracy metrics are never displayed for demo days.

| Day | Date | Forecast Strip Headline | Booked vs Expected New | Product Breakdown | Actual Units Due (D+1..D+7) | Actual Units Placed (D+1..D+7) |
| :--- | :--- | :--- | :--- | :--- | :---: | :---: |
| Day 1 | 2026-01-01 | Next 7 days: expected demand ~146 units due (likely range 133–161) | 117 already booked + ~29 expected new orders | Widget Model X: ~39u due (31 booked + ~8 new) | Widget Model Y: ~108u due (86 booked + ~22 new) | 223u (X=113, Y=110) | 118u (X=90, Y=28) |
| Day 2 | 2026-01-02 | Next 7 days: expected demand ~136 units due (likely range 120–155) | 99 already booked + ~37 expected new orders | Widget Model X: ~69u due (54 booked + ~15 new) | Widget Model Y: ~67u due (45 booked + ~22 new) | 185u (X=116, Y=69) | 96u (X=68, Y=28) |
| Day 3 | 2026-01-03 | Next 7 days: expected demand ~110 units due (likely range 91–130) | 69 already booked + ~41 expected new orders | Widget Model X: ~41u due (24 booked + ~17 new) | Widget Model Y: ~69u due (45 booked + ~24 new) | 151u (X=82, Y=69) | 92u (X=64, Y=28) |
| Day 4 | 2026-01-04 | Next 7 days: expected demand ~90 units due (likely range 70–112) | 46 already booked + ~44 expected new orders | Widget Model X: ~44u due (24 booked + ~20 new) | Widget Model Y: ~46u due (22 booked + ~24 new) | 124u (X=78, Y=46) | 78u (X=54, Y=24) |
| Day 5 | 2026-01-05 | Next 7 days: expected demand ~80 units due (likely range 58–104) | 32 already booked + ~48 expected new orders | Widget Model X: ~32u due (10 booked + ~22 new) | Widget Model Y: ~48u due (22 booked + ~26 new) | 96u (X=54, Y=42) | 64u (X=44, Y=20) |
| Day 6 | 2026-01-06 | Next 7 days: expected demand ~70 units due (likely range 47–96) | 18 already booked + ~52 expected new orders | Widget Model X: ~40u due (14 booked + ~26 new) | Widget Model Y: ~30u due (4 booked + ~26 new) | 64u (X=44, Y=20) | 46u (X=30, Y=16) |
| Day 7 | 2026-01-07 | Next 7 days: expected demand ~70 units due (likely range 45–98) | 14 already booked + ~56 expected new orders | Widget Model X: ~38u due (10 booked + ~28 new) | Widget Model Y: ~32u due (4 booked + ~28 new) | 46u (X=30, Y=16) | 32u (X=20, Y=12) |
| Day 8 | 2026-01-08 | Next 7 days: expected demand ~71 units due (likely range 44–100) | 12 already booked + ~59 expected new orders | Widget Model X: ~38u due (8 booked + ~30 new) | Widget Model Y: ~32u due (4 booked + ~28 new) | 32u (X=20, Y=12) | 20u (X=12, Y=8) |
| Day 9 | 2026-01-09 | Next 7 days: expected demand ~71 units due (likely range 44–102) | 10 already booked + ~61 expected new orders | Widget Model X: ~38u due (6 booked + ~32 new) | Widget Model Y: ~34u due (4 booked + ~30 new) | 20u (X=12, Y=8) | 10u (X=6, Y=4) |
| Day 10 | 2026-01-10 | Next 7 days: expected demand ~74 units due (likely range 45–106) | 10 already booked + ~64 expected new orders | Widget Model X: ~39u due (6 booked + ~33 new) | Widget Model Y: ~34u due (4 booked + ~30 new) | 10u (X=6, Y=4) | 0u (X=0, Y=0) |

---

## 3. Purchase Orders Status Ledger (Days 1–10)

| PO ID | Supplier | Material | Qty | Expected | Status across Days 1–10 |
| :---: | :--- | :--- | :---: | :---: | :--- |
| **#18** | EastCoast Components (S4) | Steel Rod 10mm (101) | 407 | 2025-08-14 | Cancelled on 2025-12-31 baseline reset (0 received, 139d overdue at Dec 31) |
| **#19** | EastCoast Components (S4) | Steel Rod 10mm (101) | 400 | 2026-01-02 | Overdue Days 3–7 (1d to 5d overdue); Received in full (400 kg) on Day 8 (GR #25) |
| **#20** | Global Polymers Co (S3) | Plastic Granules (102) | 250 | 2026-01-04 | 150 kg (60%) received Day 4 (GR #23); 100 kg overdue Days 5–7; completed Day 8 (GR #26) |
| **#21** | Copper & Co (S5) | Copper Wire (103) | 200 | 2026-01-06 | Received in full (200 m) on Day 6 (GR #24) on expected date |
| **#22** | Global Polymers Co (S3) | Plastic Granules (102) | 150 | 2026-01-10 | Placed Day 8 (2026-01-08); Pending on Day 10 (0 received, expected today) |

---

## 4. Complete Sales Orders Ledger (2025 Standing + 2026 Ingested)

| Order ID | Placed Date | Requested Date | Product | Qty | Shipped Date | Final Status | Source Provenance | Pack CSV SHA256 |
| :---: | :---: | :---: | :--- | :---: | :---: | :---: | :--- | :--- |
| SO #220 | 2025-12-25 | 2026-01-02 | Widget Model Y (202) | 13u | Unshipped (Backordered) | Backorder | 2025 Baseline Ledger (live/sage_live_baseline.db) | `197954063390…` |
| SO #221 | 2025-12-25 | 2026-01-02 | Widget Model Y (202) | 8u | Unshipped (Backordered) | Backorder | 2025 Baseline Ledger (live/sage_live_baseline.db) | `197954063390…` |
| SO #224 | 2025-12-29 | 2026-01-04 | Widget Model Y (202) | 14u | Unshipped (Backordered) | Backorder | 2025 Baseline Ledger (live/sage_live_baseline.db) | `197954063390…` |
| SO #225 | 2025-12-29 | 2026-01-02 | Widget Model Y (202) | 12u | Unshipped (Backordered) | Backorder | 2025 Baseline Ledger (live/sage_live_baseline.db) | `197954063390…` |
| SO #226 | 2025-12-29 | 2026-01-02 | Widget Model Y (202) | 9u | Unshipped (Backordered) | Backorder | 2025 Baseline Ledger (live/sage_live_baseline.db) | `197954063390…` |
| SO #227 | 2025-12-30 | 2026-01-03 | Widget Model X (201) | 12u | Unshipped (Backordered) | Backorder | 2025 Baseline Ledger (live/sage_live_baseline.db) | `197954063390…` |
| SO #228 | 2025-12-30 | 2026-01-06 | Widget Model Y (202) | 18u | Unshipped (Backordered) | Backorder | 2025 Baseline Ledger (live/sage_live_baseline.db) | `197954063390…` |
| SO #229 | 2025-12-30 | 2026-01-05 | Widget Model X (201) | 14u | Unshipped (Backordered) | Backorder | 2025 Baseline Ledger (live/sage_live_baseline.db) | `197954063390…` |
| SO #230 | 2025-12-31 | 2026-01-04 | Widget Model Y (202) | 9u | Unshipped (Backordered) | Backorder | 2025 Baseline Ledger (live/sage_live_baseline.db) | `197954063390…` |
| SO #231 | 2026-01-01 | 2026-01-02 | Widget Model X (201) | 5u | 2026-01-02 | Delivered | demo_data/packs/2026-01-01/sales_orders.csv | `9db69b75ff32…` |
| SO #232 | 2026-01-01 | 2026-01-02 | Widget Model Y (202) | 3u | 2026-01-02 | Delivered | demo_data/packs/2026-01-01/sales_orders.csv | `9db69b75ff32…` |
| SO #233 | 2026-01-02 | 2026-01-03 | Widget Model X (201) | 16u | 2026-01-03 | Delivered | demo_data/packs/2026-01-02/sales_orders.csv | `41f297e6c322…` |
| SO #234 | 2026-01-02 | 2026-01-03 | Widget Model X (201) | 12u | 2026-01-03 | Delivered | demo_data/packs/2026-01-02/sales_orders.csv | `41f297e6c322…` |
| SO #235 | 2026-01-02 | 2026-01-03 | Widget Model Y (202) | 4u | 2026-01-03 | Delivered | demo_data/packs/2026-01-02/sales_orders.csv | `41f297e6c322…` |
| SO #236 | 2026-01-03 | 2026-01-04 | Widget Model X (201) | 10u | 2026-01-04 | Delivered | demo_data/packs/2026-01-03/sales_orders.csv | `f6b7a2f18406…` |
| SO #237 | 2026-01-03 | 2026-01-04 | Widget Model Y (202) | 4u | 2026-01-04 | Delivered | demo_data/packs/2026-01-03/sales_orders.csv | `f6b7a2f18406…` |
| SO #238 | 2026-01-04 | 2026-01-05 | Widget Model X (201) | 10u | 2026-01-05 | Delivered | demo_data/packs/2026-01-04/sales_orders.csv | `9e6cd735a31d…` |
| SO #239 | 2026-01-04 | 2026-01-05 | Widget Model Y (202) | 4u | 2026-01-05 | Delivered | demo_data/packs/2026-01-04/sales_orders.csv | `9e6cd735a31d…` |
| SO #240 | 2026-01-05 | 2026-01-06 | Widget Model X (201) | 10u | 2026-01-06 | Delivered | demo_data/packs/2026-01-05/sales_orders.csv | `46a9cad9a827…` |
| SO #241 | 2026-01-05 | 2026-01-06 | Widget Model Y (202) | 4u | 2026-01-06 | Delivered | demo_data/packs/2026-01-05/sales_orders.csv | `46a9cad9a827…` |
| SO #242 | 2026-01-06 | 2026-01-07 | Widget Model X (201) | 8u | 2026-01-07 | Delivered | demo_data/packs/2026-01-06/sales_orders.csv | `d3ad5d6ccd7f…` |
| SO #243 | 2026-01-06 | 2026-01-07 | Widget Model X (201) | 6u | 2026-01-07 | Delivered | demo_data/packs/2026-01-06/sales_orders.csv | `d3ad5d6ccd7f…` |
| SO #244 | 2026-01-06 | 2026-01-07 | Widget Model Y (202) | 4u | 2026-01-07 | Delivered | demo_data/packs/2026-01-06/sales_orders.csv | `d3ad5d6ccd7f…` |
| SO #245 | 2026-01-07 | 2026-01-08 | Widget Model X (201) | 10u | 2026-01-08 | Delivered | demo_data/packs/2026-01-07/sales_orders.csv | `e22ebc800b4b…` |
| SO #246 | 2026-01-07 | 2026-01-08 | Widget Model Y (202) | 4u | 2026-01-08 | Delivered | demo_data/packs/2026-01-07/sales_orders.csv | `e22ebc800b4b…` |
| SO #247 | 2026-01-08 | 2026-01-09 | Widget Model X (201) | 8u | 2026-01-09 | Delivered | demo_data/packs/2026-01-08/sales_orders.csv | `8a10194911af…` |
| SO #248 | 2026-01-08 | 2026-01-09 | Widget Model Y (202) | 4u | 2026-01-09 | Delivered | demo_data/packs/2026-01-08/sales_orders.csv | `8a10194911af…` |
| SO #249 | 2026-01-09 | 2026-01-10 | Widget Model X (201) | 6u | 2026-01-10 | Delivered | demo_data/packs/2026-01-09/sales_orders.csv | `93717928b787…` |
| SO #250 | 2026-01-09 | 2026-01-10 | Widget Model Y (202) | 4u | 2026-01-10 | Delivered | demo_data/packs/2026-01-09/sales_orders.csv | `93717928b787…` |
| SO #251 | 2026-01-10 | 2026-01-11 | Widget Model X (201) | 6u | Unshipped (Backordered) | Pending | demo_data/packs/2026-01-10/sales_orders.csv | `494d6ad7289b…` |
| SO #252 | 2026-01-10 | 2026-01-11 | Widget Model Y (202) | 4u | Unshipped (Backordered) | Pending | demo_data/packs/2026-01-10/sales_orders.csv | `494d6ad7289b…` |
