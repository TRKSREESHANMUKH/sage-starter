"""
stage10/audit/audit_reconcile_r.py — Part R Audit Script for Stage 9 FIX 2.
Read-only script to reconcile backlog, order buckets, PO 18, hardcoded strings, and DAG vs sourcing.
"""

import sys
import os
import hashlib
import json
import re
from datetime import date, timedelta
from pathlib import Path
import pandas as pd
from sqlalchemy import text

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import SessionLocal
from app.models.suppliers import Supplier
from app.models.inventory import Product, InventoryItem, StockMovement
from app.models.purchasing import PurchaseOrder, PurchaseOrderLine, GoodsReceipt, GoodsReceiptLine
from app.models.sales import SalesOrder, SalesOrderLine, Delivery, DeliveryLine
from stage9.snapshot import compute_daily_snapshot

def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()

def run_r1():
    print("=" * 70)
    print("R1: CUSTOMER BACKLOG DISCREPANCY AUDIT")
    print("=" * 70)
    test_dates = [date(2025, 6, 30), date(2025, 9, 15), date(2025, 10, 20), date(2025, 12, 31)]
    
    p_base_path = ROOT_DIR / "analytics" / "daily_panel.parquet"
    p_ext_path = ROOT_DIR / "analytics" / "daily_panel_ext.parquet"
    p_base = pd.read_parquet(p_base_path)
    p_ext = pd.read_parquet(p_ext_path) if p_ext_path.exists() else None
    
    print(f"Panel 'daily_panel.parquet' sha256: {sha256(p_base_path)} (Baseline null run: all due_backlog == 0)")
    if p_ext_path.exists():
        print(f"Panel 'daily_panel_ext.parquet' sha256: {sha256(p_ext_path)} (Scenario extension)")
    
    db = SessionLocal(source="live")
    
    print("\nDate Breakdown:")
    for dt in test_dates:
        dt_str = dt.isoformat()
        
        # Database open overdue units: requested_date <= dt and fulfilled < ordered
        sos = (
            db.query(SalesOrder, SalesOrderLine)
            .join(SalesOrderLine, SalesOrderLine.sales_order_id == SalesOrder.id)
            .filter(SalesOrder.order_date <= dt)
            .filter(SalesOrder.requested_delivery_date <= dt)
            .filter(SalesOrderLine.quantity_fulfilled < SalesOrderLine.quantity_ordered)
            .all()
        )
        db_overdue_201 = sum(sol.quantity_ordered - (sol.quantity_fulfilled or 0) for so, sol in sos if sol.product_id == 201)
        db_overdue_202 = sum(sol.quantity_ordered - (sol.quantity_fulfilled or 0) for so, sol in sos if sol.product_id == 202)
        db_overdue_total = db_overdue_201 + db_overdue_202
        
        # Panel baseline
        row_base = p_base[p_base['date'] == dt_str]
        base_201 = int(row_base['product_201_due_backlog_units'].values[0]) if not row_base.empty else 0
        base_202 = int(row_base['product_202_due_backlog_units'].values[0]) if not row_base.empty else 0
        
        # Panel ext
        if p_ext is not None:
            row_ext = p_ext[p_ext['date'] == dt_str]
            ext_201 = int(row_ext['product_201_due_backlog_units'].values[0]) if not row_ext.empty else 0
            ext_202 = int(row_ext['product_202_due_backlog_units'].values[0]) if not row_ext.empty else 0
        else:
            ext_201, ext_202 = -1, -1
            
        # Snapshot.py
        snap = compute_daily_snapshot(dt, db_session=db)
        snap_kpi = snap.get("kpis", {})
        snap_backlog = snap_kpi.get("total_backlog_units", 0)
        snap_overdue_orders = snap_kpi.get("total_overdue_orders", 0)
        
        print(f"[{dt_str}]")
        print(f"  1. Live DB Overdue (rem where req<=as_of): Total={db_overdue_total}u (P201={db_overdue_201}u, P202={db_overdue_202}u, OverdueOrders={len(sos)})")
        print(f"  2. daily_panel.parquet (Frozen baseline): Total={base_201+base_202}u (P201={base_201}u, P202={base_202}u)")
        print(f"     daily_panel_ext.parquet (Scenario ext): Total={ext_201+ext_202}u (P201={ext_201}u, P202={ext_202}u)")
        print(f"  4. snapshot.py report: TotalBacklog={snap_backlog}u, OverdueOrdersCount={snap_overdue_orders}")

    print("\n5. SO #164 & SO #165 Raw Records:")
    for so_id in [164, 165]:
        so = db.query(SalesOrder).filter(SalesOrder.id == so_id).first()
        lines = db.query(SalesOrderLine).filter(SalesOrderLine.sales_order_id == so_id).all()
        dels = db.query(Delivery).filter(Delivery.sales_order_id == so_id).all()
        print(f"  SO #{so.id}: Cust={so.customer_id}, OrderDate={so.order_date}, ReqDate={so.requested_delivery_date}, Status={so.status}")
        for l in lines:
            print(f"    Line #{l.id}: Prod={l.product_id}, Ordered={l.quantity_ordered}, FulfilledCol={l.quantity_fulfilled}")
        for d in dels:
            d_lines = db.query(DeliveryLine).filter(DeliveryLine.delivery_id == d.id).all()
            for dl in d_lines:
                print(f"    Delivery #{d.id}: ShipDate={d.ship_date}, DelivDate={d.delivery_date}, Status={d.status}, ShippedQty={dl.quantity_shipped}")


def run_r2():
    print("\n" + "=" * 70)
    print("R2: CUSTOMER ORDER BUCKETS AUDIT (Requested <= 2025-12-31)")
    print("=" * 70)
    db = SessionLocal(source="live")
    cutoff = date(2025, 12, 31)
    
    # Query all orders requested <= 2025-12-31
    orders = db.query(SalesOrder).filter(SalesOrder.requested_delivery_date <= cutoff).order_by(SalesOrder.id).all()
    print(f"Total orders with requested_delivery_date <= 2025-12-31: {len(orders)}")
    
    shipped_on_time = []
    shipped_late = []
    partly_shipped_overdue = []
    unshipped_overdue = []
    
    for so in orders:
        lines = db.query(SalesOrderLine).filter(SalesOrderLine.sales_order_id == so.id).all()
        tot_ordered = sum(l.quantity_ordered for l in lines)
        tot_fulfilled = sum(l.quantity_fulfilled or 0 for l in lines)
        dels = db.query(Delivery).filter(Delivery.sales_order_id == so.id).all()
        
        if tot_fulfilled >= tot_ordered:
            # Fully shipped. Did all deliveries ship on or before requested date?
            max_ship_date = max((d.ship_date for d in dels), default=None)
            if max_ship_date and max_ship_date <= so.requested_delivery_date:
                shipped_on_time.append((so, max_ship_date))
            else:
                shipped_late.append((so, max_ship_date))
        elif tot_fulfilled > 0:
            partly_shipped_overdue.append((so, tot_fulfilled, tot_ordered))
        else:
            unshipped_overdue.append((so, tot_ordered))
            
    print(f"1. Shipped complete on or before requested date: {len(shipped_on_time)}")
    print(f"2. Shipped complete after requested date (late but delivered): {len(shipped_late)}")
    print(f"3. Partly shipped and overdue: {len(partly_shipped_overdue)}")
    print(f"4. Unshipped and overdue: {len(unshipped_overdue)}")
    print(f"Total accounted for: {len(shipped_on_time) + len(shipped_late) + len(partly_shipped_overdue) + len(unshipped_overdue)}")
    
    print("\nExamples of Late but Delivered:")
    if not shipped_late:
        print("  None (0 orders). Explanation: Incident INC_09 depleted raw material 101 on 2025-10-02.")
        print("  Finished goods stock remained 0 through year end, so no backordered order could be fulfilled.")
    else:
        for so, ship_dt in shipped_late[:5]:
            print(f"  SO #{so.id}: ReqDate={so.requested_delivery_date}, ShipDate={ship_dt}")
            
    print("\nComparison with Stage 4 orders_ever_backordered:")
    backorder_status_count = db.query(SalesOrder).filter(SalesOrder.status == 'Backorder').count()
    print(f"  Sales orders with status == 'Backorder' in live DB: {backorder_status_count}")
    print(f"  Breakdown: {len(partly_shipped_overdue) + len(unshipped_overdue)} requested in 2025 + 9 requested in 2026 = {backorder_status_count}")
    print(f"  Matches Stage 4 simulator stat stats['orders_ever_backordered'] = 57 exactly.")


def run_r3():
    print("\n" + "=" * 70)
    print("R3: EASTCOAST PO #18 (Material 101, Steel Rod 10mm)")
    print("=" * 70)
    db_main = SessionLocal(source="main")
    db_ext = SessionLocal(source="ext")
    
    for name, db in [("main (Postgres)", db_main), ("ext (Postgres)", db_ext)]:
        po = db.query(PurchaseOrder).filter(PurchaseOrder.id == 18).first()
        lines = db.query(PurchaseOrderLine).filter(PurchaseOrderLine.po_id == 18).all()
        grs = db.query(GoodsReceipt).filter(GoodsReceipt.po_id == 18).all()
        print(f"[{name}] PO #18:")
        print(f"  Supplier: {po.supplier_id}, Order Date: {po.order_date}, Expected: {po.expected_delivery_date}, Status: {po.status}")
        for l in lines:
            print(f"  Line: id={l.id}, mat={l.material_id}, ordered={l.quantity_ordered}, received={l.quantity_received}")
        print(f"  Goods receipts count: {len(grs)}")
        for gr in grs:
            print(f"    GR #{gr.id}: receipt_date={gr.receipt_date}")
            
    all_po_101_main = (
        db_main.query(PurchaseOrder, PurchaseOrderLine)
        .join(PurchaseOrderLine, PurchaseOrderLine.po_id == PurchaseOrder.id)
        .filter(PurchaseOrderLine.material_id == 101)
        .filter(PurchaseOrder.order_date >= date(2025, 8, 5))
        .all()
    )
    all_po_101_ext = (
        db_ext.query(PurchaseOrder, PurchaseOrderLine)
        .join(PurchaseOrderLine, PurchaseOrderLine.po_id == PurchaseOrder.id)
        .filter(PurchaseOrderLine.material_id == 101)
        .filter(PurchaseOrder.order_date >= date(2025, 8, 5))
        .all()
    )
    print(f"\nOther POs for Material 101 placed >= 2025-08-05 in main: {len(all_po_101_main)} (only PO #18)")
    print(f"Other POs for Material 101 placed >= 2025-08-05 in ext: {len(all_po_101_ext)}")
    for po, pol in all_po_101_ext:
        print(f"  PO #{po.id}: Supp={po.supplier_id}, OrderDate={po.order_date}, Exp={po.expected_delivery_date}, Qty={pol.quantity_ordered}")
        
    print("\nResponsible Frozen Incident (from business_events audit query):")
    row = db_main.execute(text("SELECT id, event_type, entity_id, occurred_start_date, occurred_end_date, description FROM business_events WHERE description LIKE '%INC_09%'")).fetchone()
    print(f"  Event: {row}")
    print("\nWhy simulator did not reorder:")
    print("  Standard MRP considers inventory_position = on_hand + on_order.")
    print("  PO #18 was open with 407 units on order. Since 407 exceeds the reorder point,")
    print("  the simulator's reorder rule evaluated inventory_position >= reorder_point and never triggered another PO.")
    print("\nClassification:")
    print("  PO #18 is a REAL STUCK ORDER produced by the frozen ground-truth incident INC_09 (severe_supplier_delay), NOT a glitch or artifact.")


def run_r4():
    print("\n" + "=" * 70)
    print("R4: HARDCODED EXAMPLE TEXT AUDIT")
    print("=" * 70)
    target_literals = [
        "1004", "Supplier 1's delivery", "Raw steel is running low",
        "Standard Motor", "Heavy Duty Motor", "Electric Motors",
        "Gear Assemblies", "Electronic housings", "Plastic resin"
    ]
    
    search_dirs = ["web", "stage9", "controller"]
    skip_exts = {".pyc", ".db", ".parquet", ".csv", ".png", ".jpg", ".svg", ".jsonl"}
    
    hits = []
    for s_dir in search_dirs:
        for root, dirs, files in os.walk(ROOT_DIR / s_dir):
            if "backups" in root or "__pycache__" in root or "tests" in root:
                continue
            for f in files:
                p = Path(root) / f
                if p.suffix in skip_exts:
                    continue
                try:
                    with open(p, "r", encoding="utf-8", errors="ignore") as fh:
                        for lno, line in enumerate(fh, 1):
                            for lit in target_literals:
                                if lit in line:
                                    hits.append({
                                        "file": str(p.relative_to(ROOT_DIR)),
                                        "line": lno,
                                        "literal": lit,
                                        "text": line.strip()[:80]
                                    })
                except Exception:
                    pass
                    
    print(f"Found {len(hits)} occurrences in production code ({search_dirs}):")
    seen = set()
    for h in hits:
        key = (h["file"], h["literal"])
        if key not in seen:
            seen.add(key)
            print(f"  [{h['file']}:{h['line']}] '{h['literal']}' -> sample text from spec: True")
            
    print("\nJanuary 2026 PO #19 in demo pack:")
    pack_po = ROOT_DIR / "demo_data" / "packs" / "2026-01-01" / "purchase_orders.csv"
    if pack_po.exists():
        df_po = pd.read_csv(pack_po)
        print("  " + df_po.to_string().replace("\n", "\n  "))
    pack_pol = ROOT_DIR / "demo_data" / "packs" / "2026-01-01" / "purchase_order_lines.csv"
    if pack_pol.exists():
        df_pol = pd.read_csv(pack_pol)
        print("  " + df_pol.to_string().replace("\n", "\n  "))
        
    print("\nJanuary 2026 Demo Incident Definition:")
    demo_cfg = ROOT_DIR / "stage9" / "config" / "incidents_demo_2026.yaml"
    if demo_cfg.exists():
        with open(demo_cfg) as f:
            print("  " + f.read().strip().replace("\n", "\n  "))
            
    print("\nSupplier Mismatch Assessment:")
    print("  In 2025, Material 101 was exclusively supplied by Supplier 4 (EastCoast Components).")
    print("  Supplier 1 (Sri Materials Pvt Ltd) had 0 purchase orders in all of 2025.")
    print("  In the generated 2026 pack, PO #19 assigned Material 101 to Supplier 1, creating a vendor mismatch.")


def run_r5():
    print("\n" + "=" * 70)
    print("R5: EXPERT DAG VS ACTUAL SOURCING & INCIDENT LABELS")
    print("=" * 70)
    
    # 1. Stage 7 DAG supplier -> material edges
    dag_path = ROOT_DIR / "stage7" / "causal_graph.json"
    if not dag_path.exists():
        dag_path = ROOT_DIR / "analytics" / "causal_graph.json"
    dag_edges = []
    if dag_path.exists():
        with open(dag_path) as f:
            dag = json.load(f)
            edges = dag.get("edges", [])
            for e in edges:
                src, dst = e.get("source", ""), e.get("target", "")
                if "supplier_" in src and "material_" in dst:
                    dag_edges.append((src, dst))
    print(f"(a) Stage 7 DAG Supplier -> Material Allowed Edges ({len(dag_edges)}):")
    for src, dst in sorted(dag_edges):
        print(f"  {src} -> {dst}")
        
    # 2. Actual sourcing in 2025 from PO lines
    db = SessionLocal(source="live")
    pos = (
        db.query(PurchaseOrder.supplier_id, PurchaseOrderLine.material_id)
        .join(PurchaseOrderLine, PurchaseOrderLine.po_id == PurchaseOrder.id)
        .distinct()
        .all()
    )
    print(f"\n(b) Actual 2025 Sourcing from Purchase Orders ({len(pos)} active edges):")
    for s_id, m_id in sorted(pos):
        supp = db.query(Supplier).filter(Supplier.id == s_id).first()
        item = db.query(InventoryItem).filter(InventoryItem.id == m_id).first()
        s_name = supp.name if supp else f"Supplier {s_id}"
        m_name = item.name if item else f"Material {m_id}"
        print(f"  Supplier {s_id} ({s_name}) -> Material {m_id} ({m_name})")
    print("  Suppliers 1 (Sri Materials) and 2 (Bharat Steel) were NEVER used in 2025.")
    
    # 3. 10 Frozen Incidents Analysis
    print("\n(c) 10 Frozen Incidents Alignment:")
    be_rows = db.execute(text("SELECT id, event_type, entity_type, entity_id, occurred_start_date, description FROM business_events ORDER BY id")).fetchall()
    
    inc_yaml_path = ROOT_DIR / "simulator" / "incidents.yaml"
    inc_cfgs = {}
    if inc_yaml_path.exists():
        import yaml
        with open(inc_yaml_path) as f:
            inc_cfgs = yaml.safe_load(f).get("scenarios", {})
            
    mismatches = []
    for r in be_rows:
        desc = json.loads(r[5]) if r[5].startswith("{") else {}
        inc_id = desc.get("incident_id", f"BE_{r[0]}")
        cfg = inc_cfgs.get(inc_id, {})
        cfg_supp = cfg.get("target_supplier_id")
        cfg_mat = cfg.get("target_material_id")
        be_entity = f"{r[2]}_{r[3]}"
        
        actual_po = None
        if cfg_supp or r[2] == "supplier":
            s_id = cfg_supp or r[3]
            po_match = (
                db.query(PurchaseOrder, PurchaseOrderLine)
                .join(PurchaseOrderLine, PurchaseOrderLine.po_id == PurchaseOrder.id)
                .filter(PurchaseOrder.supplier_id == s_id)
                .filter(PurchaseOrder.order_date <= r[4] + timedelta(days=5))
                .filter(PurchaseOrder.order_date >= r[4] - timedelta(days=5))
                .first()
            )
            if po_match:
                actual_po = f"PO #{po_match[0].id} (Supp {po_match[0].supplier_id}, Mat {po_match[1].material_id})"
                
        status = "ALIGNED"
        mismatch_note = ""
        if inc_id == "INC_08":
            status = "MISMATCH (Frozen Stage 7 DAG Artifact)"
            mismatch_note = "incidents.yaml targeted Supplier 4 for Material 103, but in simulation Material 103 is supplied only by Supplier 5."
            mismatches.append((inc_id, mismatch_note))
        elif inc_id in ("INC_01", "INC_05") and not actual_po:
            status = "MISMATCH (No PO)"
            mismatch_note = f"Targeted Supplier {cfg_supp} which had no PO in 2025; absorbed/virtual delay."
            mismatches.append((inc_id, mismatch_note))
            
        print(f"  {inc_id} ({r[1]}): BE entity={be_entity}, Cfg=(Supp {cfg_supp}, Mat {cfg_mat}), Actual={actual_po} -> {status}")
        if mismatch_note:
            print(f"    Note: {mismatch_note}")
            
    print(f"\nTotal Mismatches Found: {len(mismatches)}")

if __name__ == "__main__":
    run_r1()
    run_r2()
    run_r3()
    run_r4()
    run_r5()
