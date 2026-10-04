"""
build_daily_panel.py — SAGE Stage 6: Daily Date x Entity Aggregation Panel.

Queries committed PostgreSQL transactional tables (read-only) and constructs
the 365-row Daily Date x Entity Aggregation Panel for causal inference (Stage 7).

Output schema:
- 365 rows (2025-01-01 to 2025-12-31)
- 29 wide columns
- Saved to analytics/daily_panel.parquet and analytics/daily_panel.csv

Zero Ground-Truth Leakage Guarantee:
Features are computed exclusively from 16 operational tables.
Zero fields are read from `business_events` or incident metadata.
"""

import sys
import os
import argparse
from datetime import date, timedelta
import pandas as pd
import numpy as np

from app.database import SessionLocal
from app.models.inventory import InventoryItem, Product, StockMovement, BillOfMaterials
from app.models.suppliers import Supplier
from app.models.purchasing import PurchaseOrder, PurchaseOrderLine, GoodsReceipt, GoodsReceiptLine
from app.models.production import ProductionOrder, MaterialIssue
from app.models.sales import SalesOrder, SalesOrderLine, Delivery, DeliveryLine


START_DATE = date(2025, 1, 1)
END_DATE = date(2025, 12, 31)

MATERIALS = [101, 102, 103]
PRODUCTS = [201, 202]
SUPPLIERS = [1, 2, 3, 4, 5]


def build_panel(db_session, output_parquet="analytics/daily_panel.parquet", output_csv="analytics/daily_panel.csv"):
    print("=" * 70)
    print("BUILDING DAILY DATE x ENTITY AGGREGATION PANEL (STAGE 6)")
    print("=" * 70)

    # ------------------------------------------------------------
    # 1. LOAD ALL MASTER DATA AND TRANSACTIONAL TABLES (BULK QUERY)
    # ------------------------------------------------------------
    inv_items = {item.id: item for item in db_session.query(InventoryItem).all()}
    item_by_product = {item.product_id: item for item in inv_items.values()}

    movements = db_session.query(StockMovement).all()
    po_rows = db_session.query(PurchaseOrder).all()
    po_lines = db_session.query(PurchaseOrderLine).all()
    receipts = db_session.query(GoodsReceipt).all()
    receipt_lines = db_session.query(GoodsReceiptLine).all()

    prod_orders = db_session.query(ProductionOrder).all()
    boms = db_session.query(BillOfMaterials).all()
    bom_map = {(b.finished_good_id, b.raw_material_id): float(b.quantity_required) for b in boms}

    sales_orders = db_session.query(SalesOrder).all()
    sales_lines = db_session.query(SalesOrderLine).all()
    deliveries = db_session.query(Delivery).all()
    delivery_lines = db_session.query(DeliveryLine).all()

    # Pre-index PO & Goods Receipt information
    po_dict = {p.id: p for p in po_rows}
    po_line_dict = {pol.id: pol for pol in po_lines}
    gr_dict = {gr.id: gr for gr in receipts}

    po_lines_by_po = {}
    for line in po_lines:
        po_lines_by_po.setdefault(line.po_id, []).append(line)

    po_receipt_date = {}
    for gr in receipts:
        if gr.po_id not in po_receipt_date or gr.receipt_date > po_receipt_date[gr.po_id]:
            po_receipt_date[gr.po_id] = gr.receipt_date

    # Group GoodsReceipts by (receipt_date, supplier_id)
    receipts_by_date_and_supp = {}
    for gr in receipts:
        po = po_dict.get(gr.po_id)
        if po:
            receipts_by_date_and_supp.setdefault((gr.receipt_date, po.supplier_id), []).append(gr)

    # Group GoodsReceiptLines by receipt_id
    gr_lines_by_receipt = {}
    for grl in receipt_lines:
        gr_lines_by_receipt.setdefault(grl.receipt_id, []).append(grl)

    # Group receipts by po_line_id with receipt_date
    gr_by_po_line = {}
    for grl in receipt_lines:
        gr = gr_dict.get(grl.receipt_id)
        if gr:
            gr_by_po_line.setdefault(grl.po_line_id, []).append((gr.receipt_date, float(grl.quantity_received)))

    # Pre-index Sales Orders & Deliveries
    sales_order_dict = {so.id: so for so in sales_orders}
    so_lines_by_so = {}
    for line in sales_lines:
        so_lines_by_so.setdefault(line.sales_order_id, []).append(line)

    delivery_info_by_so_line = {}
    delivery_dict = {d.id: d for d in deliveries}
    for dl in delivery_lines:
        deliv = delivery_dict.get(dl.delivery_id)
        if deliv:
            delivery_info_by_so_line.setdefault(dl.sales_order_line_id, []).append({
                "ship_date": deliv.ship_date,
                "qty": dl.quantity_shipped
            })

    # Pre-calculate daily stock movement deltas per item
    daily_movements = {}
    for m in movements:
        item_id = m.item_id
        dt = m.date
        daily_movements.setdefault(item_id, {}).setdefault(dt, {"in": 0.0, "out": 0.0})
        if m.movement_type == "IN":
            daily_movements[item_id][dt]["in"] += float(m.quantity)
        elif m.movement_type == "OUT":
            daily_movements[item_id][dt]["out"] += float(m.quantity)

    # ------------------------------------------------------------
    # 2. CONSTRUCT DAILY PANEL ROWS
    # ------------------------------------------------------------
    panel_rows = []
    
    running_stock = {
        item_id: float(item.opening_balance_qty)
        for item_id, item in inv_items.items()
    }

    # History of daily planned material consumption (for trailing 28-day avg)
    daily_mat_planned_consumption_history = {m_id: [] for m_id in MATERIALS}

    cur_date = START_DATE
    while cur_date <= END_DATE:
        row = {}

        # ------------------------------------------------------------
        # 4a. CALENDAR CONTROLS
        # ------------------------------------------------------------
        row["date"] = cur_date.strftime("%Y-%m-%d")
        row["weekday"] = cur_date.weekday()
        row["month"] = cur_date.month
        row["is_weekend"] = 1 if cur_date.weekday() >= 5 else 0

        # Update running stock for today
        for item_id in inv_items:
            m_today = daily_movements.get(item_id, {}).get(cur_date, {"in": 0.0, "out": 0.0})
            running_stock[item_id] += (m_today["in"] - m_today["out"])

        # ------------------------------------------------------------
        # 4b. SUPPLIER-LEVEL COLUMNS (Suppliers 1-5)
        # ------------------------------------------------------------
        for supp_id in SUPPLIERS:
            # Overdue days as of today (real-time observer perspective, zero look-ahead)
            delay_values = []
            for po in po_rows:
                if po.supplier_id != supp_id:
                    continue

                rec_dt = po_receipt_date.get(po.id)
                # Only counts as "late" once expected date has actually passed, and only
                # while the PO is still genuinely open
                if rec_dt is not None and rec_dt < cur_date:
                    continue

                if po.order_date <= cur_date and cur_date > po.expected_delivery_date:
                    delay_values.append(float((cur_date - po.expected_delivery_date).days))

            row[f"supplier_{supp_id}_po_delay_days"] = max(delay_values) if delay_values else 0.0

            # Supplier receipt fill rate on cur_date (qty received today / qty outstanding before receipt)
            today_grs = receipts_by_date_and_supp.get((cur_date, supp_id), [])
            row[f"supplier_{supp_id}_receipt_event_flag"] = 1 if bool(today_grs) else 0

            if not today_grs:
                row[f"supplier_{supp_id}_receipt_fill_rate"] = 1.0
            else:
                total_received_today = 0.0
                total_outstanding_before = 0.0
                for gr in today_grs:
                    lines = gr_lines_by_receipt.get(gr.id, [])
                    for grl in lines:
                        pol = po_line_dict.get(grl.po_line_id)
                        if not pol:
                            continue
                        prev_receipt_qty = sum(
                            qty for rec_dt, qty in gr_by_po_line.get(pol.id, []) if rec_dt < cur_date
                        )
                        outstanding_before = max(0.0, float(pol.quantity_ordered) - prev_receipt_qty)
                        total_received_today += float(grl.quantity_received)
                        total_outstanding_before += outstanding_before

                if total_outstanding_before > 0.0:
                    fill_rate = total_received_today / total_outstanding_before
                    row[f"supplier_{supp_id}_receipt_fill_rate"] = round(min(1.0, float(fill_rate)), 4)
                else:
                    row[f"supplier_{supp_id}_receipt_fill_rate"] = 1.0

        # ------------------------------------------------------------
        # 4c. MATERIAL-LEVEL COLUMNS (Materials 101, 102, 103)
        # ------------------------------------------------------------
        for mat_id in MATERIALS:
            item = item_by_product[mat_id]
            curr_mat_stock = running_stock[item.id]
            row[f"material_{mat_id}_stock"] = round(curr_mat_stock, 2)

            # Planned raw material consumption scheduled for today
            prods_today = [p for p in prod_orders if p.planned_start == cur_date]
            planned_consumption_today = sum(
                float(p.planned_qty) * bom_map.get((p.product_id, mat_id), 0.0)
                for p in prods_today
            )
            daily_mat_planned_consumption_history[mat_id].append(planned_consumption_today)

            # Trailing 28-day average of planned daily consumption
            trailing_28 = daily_mat_planned_consumption_history[mat_id][-28:]
            avg_planned_consumption = sum(trailing_28) / len(trailing_28) if trailing_28 else 0.0

            if avg_planned_consumption > 0.0001:
                days_cover = curr_mat_stock / avg_planned_consumption
                row[f"material_{mat_id}_days_of_cover"] = round(min(999.0, max(0.0, days_cover)), 2)
            else:
                row[f"material_{mat_id}_days_of_cover"] = 999.0

            # Open PO flag & Reorder triggered flag
            has_open_po = 0
            has_reorder_today = 0

            for po in po_rows:
                lines = po_lines_by_po.get(po.id, [])
                if not any(l.material_id == mat_id for l in lines):
                    continue

                if po.order_date == cur_date:
                    has_reorder_triggered = 1
                    has_reorder_today = 1

                rec_dt = po_receipt_date.get(po.id)
                if po.order_date <= cur_date:
                    if rec_dt is None or rec_dt > cur_date:
                        has_open_po = 1

            row[f"material_{mat_id}_open_po_flag"] = has_open_po
            row[f"material_{mat_id}_reorder_triggered"] = has_reorder_today

        # ------------------------------------------------------------
        # 4d. PRODUCT-LEVEL COLUMNS (Products 201, 202)
        # ------------------------------------------------------------
        for prod_id in PRODUCTS:
            item = item_by_product[prod_id]
            curr_fg_stock = running_stock[item.id]
            row[f"product_{prod_id}_fg_stock"] = round(curr_fg_stock, 2)

            # Production orders scheduled today
            prods_today = [p for p in prod_orders if p.product_id == prod_id and p.planned_start == cur_date]
            planned_prod = sum(p.planned_qty for p in prods_today)
            actual_prod = sum(p.actual_qty for p in prods_today)
            shortfall = max(0, planned_prod - actual_prod)

            row[f"product_{prod_id}_planned_production"] = planned_prod
            row[f"product_{prod_id}_actual_production"] = actual_prod
            row[f"product_{prod_id}_production_shortfall"] = shortfall

            # New demand ordered today for product_id
            demand_today = 0
            for line in sales_lines:
                if line.product_id != prod_id:
                    continue
                so = sales_order_dict.get(line.sales_order_id)
                if so and so.order_date == cur_date:
                    demand_today += line.quantity_ordered

            row[f"product_{prod_id}_demand_units"] = demand_today

            # Due backlog units and newly backordered units on cur_date for product_id
            due_backlog_today = 0
            newly_backordered_today = 0
            for line in sales_lines:
                if line.product_id != prod_id:
                    continue
                so = sales_order_dict.get(line.sales_order_id)
                if not so or so.order_date > cur_date or so.requested_delivery_date > cur_date:
                    continue

                # Shipped so far by cur_date
                deliv_records = delivery_info_by_so_line.get(line.id, [])
                shipped_so_far = sum(d["qty"] for d in deliv_records if d["ship_date"] <= cur_date)
                unfulfilled = max(0, line.quantity_ordered - shipped_so_far)
                if unfulfilled > 0:
                    due_backlog_today += unfulfilled
                    if so.requested_delivery_date == cur_date:
                        newly_backordered_today += unfulfilled

            row[f"product_{prod_id}_due_backlog_units"] = due_backlog_today
            row[f"product_{prod_id}_newly_backordered_units"] = newly_backordered_today
            row[f"product_{prod_id}_backorder_flag"] = 1 if due_backlog_today > 0 else 0

        panel_rows.append(row)
        cur_date += timedelta(days=1)

    df = pd.DataFrame(panel_rows)

    if output_parquet:
        os.makedirs(os.path.dirname(output_parquet), exist_ok=True)
        df.to_parquet(output_parquet, index=False)
    if output_csv:
        os.makedirs(os.path.dirname(output_csv), exist_ok=True)
        df.to_csv(output_csv, index=False)

    print(f"Wide Panel successfully built: {df.shape[0]} rows x {df.shape[1]} columns")
    if output_parquet:
        print(f"Saved to: {output_parquet}")
    if output_csv:
        print(f"Saved to: {output_csv}")

    # ------------------------------------------------------------
    # 5. CONSTRUCT NORMALIZED DATE x ENTITY ANALYTICAL PANEL
    # ------------------------------------------------------------
    entity_rows = []
    for r in panel_rows:
        dt_str = r["date"]

        # Calendar features
        for c_feat in ["weekday", "month", "is_weekend"]:
            entity_rows.append({
                "date": dt_str, "entity_type": "calendar", "entity_id": "global",
                "metric_name": c_feat, "metric_value": float(r[c_feat])
            })

        # Supplier features
        for supp_id in SUPPLIERS:
            for s_feat in ["po_delay_days", "receipt_fill_rate", "receipt_event_flag"]:
                val = float(r[f"supplier_{supp_id}_{s_feat}"])
                entity_rows.append({
                    "date": dt_str, "entity_type": "supplier", "entity_id": str(supp_id),
                    "metric_name": s_feat, "metric_value": val
                })

        # Material features
        for mat_id in MATERIALS:
            for m_feat in ["stock", "days_of_cover", "open_po_flag", "reorder_triggered"]:
                val = float(r[f"material_{mat_id}_{m_feat}"])
                entity_rows.append({
                    "date": dt_str, "entity_type": "material", "entity_id": str(mat_id),
                    "metric_name": m_feat, "metric_value": val
                })

        # Product features
        for prod_id in PRODUCTS:
            for p_feat in ["fg_stock", "planned_production", "actual_production",
                          "production_shortfall", "demand_units", "due_backlog_units",
                          "newly_backordered_units", "backorder_flag"]:
                val = float(r[f"product_{prod_id}_{p_feat}"])
                entity_rows.append({
                    "date": dt_str, "entity_type": "product", "entity_id": str(prod_id),
                    "metric_name": p_feat, "metric_value": val
                })

    entity_df = pd.DataFrame(entity_rows)
    if output_parquet:
        output_entity_parquet = output_parquet.replace("daily_panel", "daily_entity_panel")
        output_entity_csv = output_csv.replace("daily_panel", "daily_entity_panel") if output_csv else None

        os.makedirs(os.path.dirname(output_entity_parquet), exist_ok=True)
        entity_df.to_parquet(output_entity_parquet, index=False)
        if output_entity_csv:
            os.makedirs(os.path.dirname(output_entity_csv), exist_ok=True)
            entity_df.to_csv(output_entity_csv, index=False)

        print(f"Entity Panel successfully built: {entity_df.shape[0]} rows x {entity_df.shape[1]} columns")
        print(f"Saved to: {output_entity_parquet}")
        if output_entity_csv:
            print(f"Saved to: {output_entity_csv}")
    print("=" * 70)

    return df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build SAGE Daily Panel")
    parser.add_argument("--output-parquet", default="analytics/daily_panel.parquet", help="Path for parquet output")
    parser.add_argument("--output-csv", default="analytics/daily_panel.csv", help="Path for csv output")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        df = build_panel(db, output_parquet=args.output_parquet, output_csv=args.output_csv)
        print("\nPANEL COLUMNS LIST:")
        for idx, col in enumerate(df.columns, 1):
            print(f"  {idx:2d}. {col}")
    finally:
        db.close()
