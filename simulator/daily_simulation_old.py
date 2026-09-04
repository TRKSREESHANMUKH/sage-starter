"""
This script simulates SAGE's pretend company running day by day,
for a full year, with no incidents yet — just normal business.
"""

from datetime import date, timedelta
from app.database import SessionLocal
from app.models.suppliers import Supplier
from app.models.inventory import InventoryItem, BillOfMaterials, StockMovement
from app.models.purchasing import PurchaseOrder, PurchaseOrderLine, GoodsReceipt, GoodsReceiptLine
from app.models.production import ProductionOrder, MaterialIssue

db = SessionLocal()

START_DATE = date(2025, 1, 1)
END_DATE = date(2025, 12, 31)

inventory_items = db.query(InventoryItem).all()
suppliers = {s.id: s for s in db.query(Supplier).all()}
bom_rows = db.query(BillOfMaterials).all()

current_stock = {item.id: item.opening_balance_qty for item in inventory_items}
item_by_product = {item.product_id: item for item in inventory_items}

# Which supplier sells which raw material.
SUPPLIER_FOR_MATERIAL = {101: 1, 102: 3, 103: 2}
FINISHED_GOODS = [201, 202]

# How much to order each time we reorder a material.
REORDER_QUANTITY = {1: 2000, 2: 1500, 3: 3000}

next_po_id = 1
next_po_line_id = 1
next_receipt_id = 1
next_receipt_line_id = 1
next_prod_id = 1
next_issue_id = 1
next_movement_id = 1

# Stops us from placing a new order every day while one is already in flight.
pending_po_for_item = {item.id: None for item in inventory_items}
open_purchase_orders = {}

current_day = START_DATE
while current_day <= END_DATE:

    # STEP 1: check stock, place a reorder if low and none already pending
    for item in inventory_items:
        if item.product_id not in SUPPLIER_FOR_MATERIAL:
            continue  # finished goods aren't purchased from suppliers
        if current_stock[item.id] <= item.reorder_point and pending_po_for_item[item.id] is None:
            supplier_id = SUPPLIER_FOR_MATERIAL[item.product_id]
            supplier = suppliers[supplier_id]
            order_qty = REORDER_QUANTITY[item.id]
            expected_date = current_day + timedelta(days=supplier.base_lead_time_days)

            new_po = PurchaseOrder(
                id=next_po_id, supplier_id=supplier_id, order_date=current_day,
                expected_delivery_date=expected_date, status="Pending",
            )
            db.add(new_po)
            db.flush()

            new_po_line = PurchaseOrderLine(
                id=next_po_line_id, po_id=new_po.id, material_id=item.product_id,
                quantity_ordered=order_qty, quantity_received=None,
            )
            db.add(new_po_line)
            next_po_line_id += 1

            open_purchase_orders[new_po.id] = {
                "item_id": item.id, "quantity": order_qty,
                "expected_delivery_date": expected_date,
            }
            pending_po_for_item[item.id] = new_po.id
            print(f"{current_day}: placed PO {new_po.id} for item {item.id}, "
                  f"{order_qty} units, expected {expected_date}")
            next_po_id += 1

    # STEP 2: receive any purchase orders due today
    for po_id, info in list(open_purchase_orders.items()):
        if info["expected_delivery_date"] == current_day:
            new_receipt = GoodsReceipt(
                id=next_receipt_id, po_id=po_id, receipt_date=current_day, status="Complete",
            )
            db.add(new_receipt)
            db.flush()

            po_lines = db.query(PurchaseOrderLine).filter_by(po_id=po_id).all()
            for po_line in po_lines:
                po_line.quantity_received = po_line.quantity_ordered

                new_receipt_line = GoodsReceiptLine(
                    id=next_receipt_line_id, receipt_id=new_receipt.id, po_line_id=po_line.id,
                    material_id=po_line.material_id, quantity_received=po_line.quantity_ordered,
                )
                db.add(new_receipt_line)
                db.flush()

                new_movement = StockMovement(
                    id=next_movement_id, item_id=info["item_id"], date=current_day,
                    movement_type="IN", quantity=po_line.quantity_ordered,
                    goods_receipt_line_id=new_receipt_line.id,
                )
                db.add(new_movement)
                next_movement_id += 1

                current_stock[info["item_id"]] += po_line.quantity_ordered
                next_receipt_line_id += 1

            print(f"{current_day}: received PO {po_id}, item {info['item_id']} "
                  f"now at {current_stock[info['item_id']]}")
            next_receipt_id += 1
            pending_po_for_item[info["item_id"]] = None
            del open_purchase_orders[po_id]

    # STEP 3: run production every 5 days, limited by actual raw material stock
    if current_day.day % 5 == 0:
        for product_id in FINISHED_GOODS:
            planned_qty = 50
            recipe = [b for b in bom_rows if b.finished_good_id == product_id]

            max_producible = planned_qty
            for bom in recipe:
                raw_item = item_by_product[bom.raw_material_id]
                can_make = current_stock[raw_item.id] // bom.quantity_required
                max_producible = min(max_producible, int(can_make))
            actual_qty = max(0, max_producible)

            new_prod = ProductionOrder(
                id=next_prod_id, product_id=product_id,
                planned_start=current_day, planned_end=current_day,
                actual_start=current_day if actual_qty > 0 else None,
                actual_end=current_day if actual_qty > 0 else None,
                planned_qty=planned_qty, actual_qty=actual_qty,
                status="Completed" if actual_qty == planned_qty else "Delayed",
            )
            db.add(new_prod)
            db.flush()

            if actual_qty > 0:
                for bom in recipe:
                    raw_item = item_by_product[bom.raw_material_id]
                    planned_needed = bom.quantity_required * planned_qty
                    actual_needed = bom.quantity_required * actual_qty

                    new_issue = MaterialIssue(
                        id=next_issue_id, production_order_id=new_prod.id, item_id=raw_item.id,
                        planned_quantity=planned_needed, planned_issue_date=current_day,
                        quantity_issued=actual_needed, issue_date=current_day,
                    )
                    db.add(new_issue)
                    db.flush()

                    new_movement = StockMovement(
                        id=next_movement_id, item_id=raw_item.id, date=current_day,
                        movement_type="OUT", quantity=actual_needed, material_issue_id=new_issue.id,
                    )
                    db.add(new_movement)
                    next_movement_id += 1
                    current_stock[raw_item.id] -= actual_needed
                    next_issue_id += 1

                finished_item = item_by_product[product_id]
                fg_movement = StockMovement(
                    id=next_movement_id, item_id=finished_item.id, date=current_day,
                    movement_type="IN", quantity=actual_qty, production_order_id=new_prod.id,
                )
                db.add(fg_movement)
                next_movement_id += 1
                current_stock[finished_item.id] += actual_qty
                print(f"{current_day}: produced {actual_qty}/{planned_qty} of product {product_id}")
            else:
                print(f"{current_day}: COULD NOT PRODUCE product {product_id} -- no raw material")

            next_prod_id += 1

    current_day += timedelta(days=1)

db.commit()
db.close()
print("Loop finished.")