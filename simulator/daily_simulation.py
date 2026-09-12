import math
from datetime import date, timedelta
from fractions import Fraction
import random

from app.database import SessionLocal

from app.models.inventory import (
    Product,
    InventoryItem,
    BillOfMaterials,
    StockMovement,
)

from app.models.suppliers import Supplier

from app.models.purchasing import (
    PurchaseOrder,
    PurchaseOrderLine,
    GoodsReceipt,
    GoodsReceiptLine,
)

from app.models.production import (
    ProductionOrder,
    MaterialIssue,
)

from app.models.sales import (
    Customer,
    SalesOrder,
    SalesOrderLine,
    Delivery,
    DeliveryLine,
)

from simulator.incident_engine import IncidentEngine


# ============================================================
# CONFIGURATION
# ============================================================

START_DATE = date(2025, 1, 1)
END_DATE = date(2025, 12, 31)

SEED = 42
random.seed(SEED)

PRINT_DAILY_LOG = True

# Set to False any time you want to reproduce the old, incident-free
# baseline exactly (e.g. to re-confirm nothing broke).
INCIDENTS_ENABLED = True


# ============================================================
# DATABASE
# ============================================================

db = SessionLocal()


# ============================================================
# PRE-FLIGHT: REFUSE TO RUN ON TOP OF LEFTOVER DATA
# ============================================================

TRANSACTIONAL_MODELS = [
    PurchaseOrder, PurchaseOrderLine, GoodsReceipt, GoodsReceiptLine,
    ProductionOrder, MaterialIssue, StockMovement,
    SalesOrder, SalesOrderLine, Delivery, DeliveryLine,
]

for model in TRANSACTIONAL_MODELS:
    existing_count = db.query(model).count()
    if existing_count > 0:
        raise RuntimeError(
            f"{model.__tablename__} already contains {existing_count} row(s). "
            f"Truncate first:\n\n"
            f"docker exec -it sage_postgres psql -U sage_user -d sage_db "
            f"--pset pager=off -c \"TRUNCATE purchase_orders, "
            f"purchase_order_lines, goods_receipts, goods_receipt_lines, "
            f"production_orders, material_issues, stock_movements, "
            f"sales_orders, sales_order_lines, deliveries, delivery_lines "
            f"RESTART IDENTITY CASCADE;\""
        )


# ============================================================
# LOAD MASTER DATA
# ============================================================

inventory_items = db.query(InventoryItem).all()
products = {p.id: p for p in db.query(Product).all()}
suppliers = {s.id: s for s in db.query(Supplier).all()}
customers = db.query(Customer).all()
bom_rows = db.query(BillOfMaterials).all()

if not inventory_items:
    raise RuntimeError("No inventory items found.")

if not suppliers:
    raise RuntimeError("No suppliers found.")

if not customers:
    raise RuntimeError("No customers found.")

if len(customers) < 5:
    raise RuntimeError(f"Expected at least 5 customers, found {len(customers)}.")


item_by_product = {
    item.product_id: item
    for item in inventory_items
}


# ============================================================
# VALIDATE REQUIRED MASTER DATA BEFORE RUN
# ============================================================

REQUIRED_PRODUCTS = [101, 102, 103, 201, 202]

for product_id in REQUIRED_PRODUCTS:
    if product_id not in products:
        raise RuntimeError(f"Required product {product_id} was not found.")

    if product_id not in item_by_product:
        raise RuntimeError(f"No inventory item exists for product {product_id}.")

FINISHED_GOODS = [201, 202]
for fg in FINISHED_GOODS:
    if not any(b.finished_good_id == fg for b in bom_rows):
        raise RuntimeError(f"No Bill of Materials found for finished good {fg}.")


# ============================================================
# MATERIAL / SUPPLIER RELATIONSHIPS
# ============================================================

SUPPLIERS_FOR_MATERIAL = {
    101: [1, 2, 4],   # steel
    102: [3, 4],      # plastic
    103: [1, 5],      # copper
}

for material_id in SUPPLIERS_FOR_MATERIAL:
    valid = [s for s in SUPPLIERS_FOR_MATERIAL[material_id] if s in suppliers]
    if not valid:
        raise RuntimeError(f"No valid supplier configured for material {material_id}.")


# ============================================================
# PRODUCTION SETTINGS
# ============================================================

PRODUCTION_BATCH = {
    201: 30,
    202: 20,
}


def production_step_size(product_id):
    step = 1
    for bom in bom_rows:
        if bom.finished_good_id == product_id:
            frac = Fraction(bom.quantity_required).limit_denominator(1000)
            step = step * frac.denominator // math.gcd(step, frac.denominator)
    return step


PRODUCTION_STEP = {
    product_id: production_step_size(product_id)
    for product_id in PRODUCTION_BATCH
}

for product_id, batch in PRODUCTION_BATCH.items():
    step = PRODUCTION_STEP[product_id]
    if batch % step != 0:
        raise RuntimeError(
            f"PRODUCTION_BATCH for product {product_id} ({batch}) is not "
            f"a multiple of {step}, which its Bill of Materials requires."
        )


# ============================================================
# INITIAL STOCK
# ============================================================

current_stock = {
    item.id: float(item.opening_balance_qty)
    for item in inventory_items
}


# ============================================================
# ID COUNTERS
# ============================================================

next_po_id = 1
next_po_line_id = 1
next_receipt_id = 1
next_receipt_line_id = 1
next_prod_id = 1
next_issue_id = 1
next_movement_id = 1
next_sales_order_id = 1
next_sales_line_id = 1
next_delivery_id = 1
next_delivery_line_id = 1


# ============================================================
# OPEN ORDERS
# ============================================================

open_purchase_orders = []
open_sales_orders = []


# ============================================================
# STATISTICS
# ============================================================

stats = {
    "production_orders": 0,
    "production_completed": 0,
    "production_delayed": 0,
    "units_planned": 0,
    "units_produced": 0,
    "purchase_orders": 0,
    "purchase_receipts": 0,
    "purchase_units_ordered": 0,
    "purchase_units_received": 0,
    "sales_orders": 0,
    "sales_units_ordered": 0,
    "sales_units_fulfilled": 0,
    "sales_units_backordered": 0,
    "deliveries": 0,
    "delivery_units": 0,
}


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def log(message):
    if PRINT_DAILY_LOG:
        print(message)


def get_stock(product_id):
    item = item_by_product[product_id]
    return current_stock[item.id]


def change_stock(product_id, amount):
    item = item_by_product[product_id]
    current_stock[item.id] = round(current_stock[item.id] + amount, 4)

    if current_stock[item.id] < -0.0001:
        raise RuntimeError(
            f"Negative inventory detected for product {product_id}: "
            f"{current_stock[item.id]}"
        )


def choose_supplier(material_id):
    choices = [
        supplier_id
        for supplier_id in SUPPLIERS_FOR_MATERIAL.get(material_id, [])
        if supplier_id in suppliers
    ]

    if not choices:
        raise RuntimeError(f"No supplier configured for material {material_id}.")

    return random.choice(choices)


def production_day(current_day):
    if current_day.weekday() >= 5:
        return False
    return random.random() < 0.24


def customer_demand(customer, product_id, current_day):
    base = 12 if product_id == 201 else 9

    customer_factor = {
        1: 1.20, 2: 0.85, 3: 1.35, 4: 1.00, 5: 0.70,
    }.get(customer.id, 1.0)

    weekday_factor = {
        0: 1.00, 1: 1.10, 2: 1.05, 3: 0.95,
        4: 1.15, 5: 0.60, 6: 0.50,
    }[current_day.weekday()]

    month_factor = {
        1: 0.90, 2: 0.95, 3: 1.00, 4: 1.00, 5: 1.05, 6: 1.00,
        7: 0.95, 8: 1.05, 9: 1.10, 10: 1.15, 11: 1.20, 12: 1.30,
    }[current_day.month]

    mean = base * customer_factor * weekday_factor * month_factor
    mean *= demand_multiplier_for(product_id, current_day)

    demand = random.gauss(mean, mean * 0.15)
    demand = max(mean * 0.5, min(demand, mean * 1.6))
    return max(1, int(round(demand)))


def required_materials(product_id, quantity):
    requirements = {}
    for bom in bom_rows:
        if bom.finished_good_id == product_id:
            amount = bom.quantity_required * quantity
            if abs(amount - round(amount)) > 0.0001:
                raise RuntimeError(
                    f"Non-integral material consumption detected: "
                    f"product={product_id}, quantity={quantity}, "
                    f"material={bom.raw_material_id}, amount={amount}"
                )
            requirements[bom.raw_material_id] = int(round(amount))
    return requirements


def maximum_producible(product_id, planned_quantity):
    recipe = [b for b in bom_rows if b.finished_good_id == product_id]
    if not recipe:
        return 0

    maximum = planned_quantity
    for bom in recipe:
        available = get_stock(bom.raw_material_id)
        possible = int(available // bom.quantity_required)
        maximum = min(maximum, possible)
    maximum = (int(maximum) // PRODUCTION_STEP[product_id]) * PRODUCTION_STEP[product_id]
    return max(0, int(maximum))


# ============================================================
# INCIDENTS (Stage 4)
# ============================================================
# Generated ONCE, before the day-by-day loop starts. This list never
# changes while the simulation runs -- each day just checks which
# incidents (if any) are currently "active" and adjusts an INPUT
# (a lead time, a demand number, a capacity ceiling). The simulator's
# existing formulas do all the real work; incidents never write a
# stock/production/sales number directly.

if INCIDENTS_ENABLED:
    incident_engine = IncidentEngine(config_path="simulator/incidents.yaml")
    incidents = incident_engine.generate()
else:
    incidents = []


def active_incidents(current_day):
    """All incidents whose date window covers current_day."""
    return [inc for inc in incidents if inc["start_date"] <= current_day <= inc["end_date"]]


def supplier_incident_effect(supplier_id, current_day):
    """
    Looks at every incident active today and returns:
      extra_delay_days      -- extra days to add on top of the normal
                                lead-time calculation for a PO placed
                                today with this supplier
      forced_received_fraction -- if set, the very next receipt against
                                a PO placed today must be forced to only
                                this fraction of the ordered quantity
                                (used for the partial_receipt scenario)
    """
    extra_delay = 0
    forced_fraction = None

    for inc in active_incidents(current_day):
        touches_this_supplier = (
            inc.get("supplier_id") == supplier_id
            or supplier_id in inc.get("supplier_ids", [])
        )
        if not touches_this_supplier:
            continue

        if inc["type"] in (
            "supplier_delay",
            "severe_supplier_delay_stockout",
            "delay_absorbed_by_safety_stock",
            "overlapping_supplier_delay",
            "two_simultaneous_independent_causes",
        ):
            extra_delay += inc["duration_days"]

        if inc["type"] == "partial_receipt":
            forced_fraction = inc["received_fraction"]

    return extra_delay, forced_fraction


def product_capacity_reduction(product_id, current_day):
    """Largest active capacity_reduction fraction (0.0-1.0) affecting
    this finished product today. 0.0 means no reduction."""
    reduction = 0.0
    for inc in active_incidents(current_day):
        if inc.get("product_id") != product_id:
            continue
        if inc["type"] in ("capacity_disruption", "two_simultaneous_independent_causes"):
            reduction = max(reduction, inc.get("capacity_reduction", 0.0))
    return reduction


def demand_multiplier_for(product_id, current_day):
    """Largest active demand multiplier affecting this finished product
    today. 1.0 means no change (normal demand)."""
    multiplier = 1.0
    for inc in active_incidents(current_day):
        if inc.get("product_id") != product_id:
            continue
        if inc["type"] in ("demand_spike", "seasonal_demand"):
            multiplier = max(multiplier, inc.get("demand_multiplier", 1.0))
    return multiplier


# ------------------------------------------------------------------
# GUARANTEED SUPPLY-SIDE INCIDENT TRIGGERING
# ------------------------------------------------------------------
# Problem this section solves: 5 of the 10 required scenarios only
# have an effect if a Purchase Order for the right material happens to
# exist during the incident's short window. Natural reorder frequency
# for some materials can be too low for that overlap to happen by
# chance. So: on the exact start day of a supply-side incident, we
# guarantee a real transaction exists to carry the effect --
# preferring to modify an ALREADY-OPEN real PO if one exists, and only
# creating a new one if none does. This never fakes a downstream
# number (stock/production/sales are still fully calculated as normal)
# -- it only guarantees the upstream input (a purchase event) exists,
# which is what the whole point of these 10 frozen scenarios requires.

SUPPLY_INCIDENT_TYPES = {
    "supplier_delay",
    "severe_supplier_delay_stockout",
    "delay_absorbed_by_safety_stock",
    "overlapping_supplier_delay",
    "partial_receipt",
    "two_simultaneous_independent_causes",
}

SUPPLIER_TO_MATERIALS = {}
for _material_id, _supplier_list in SUPPLIERS_FOR_MATERIAL.items():
    for _supplier_id in _supplier_list:
        SUPPLIER_TO_MATERIALS.setdefault(_supplier_id, []).append(_material_id)


def material_needing_most_from_supplier(supplier_id):
    """Of the materials this supplier provides, pick the one closest to
    its reorder point (most realistic target for a real disruption)."""
    candidates = SUPPLIER_TO_MATERIALS.get(supplier_id, [])
    if not candidates:
        return None

    def urgency(material_id):
        item = item_by_product[material_id]
        if not item.reorder_point:
            return float("inf")
        return get_stock(material_id) / item.reorder_point

    return min(candidates, key=urgency)


def base_order_quantity(material_id):
    if material_id == 101:
        return random.randint(1600, 2600)
    elif material_id == 102:
        return random.randint(1000, 1900)
    else:
        return random.randint(1800, 3200)


def place_new_po(material_id, current_day, forced_supplier_id=None,
                  extra_delay=0, forced_fraction=None, is_forced=False):
    """The single place a new Purchase Order gets created. Used by both
    the normal reorder-point check AND the guaranteed incident trigger,
    so there is only one code path to get right."""
    global next_po_id, next_po_line_id

    supplier_id = forced_supplier_id if forced_supplier_id is not None else choose_supplier(material_id)
    supplier = suppliers[supplier_id]
    order_qty = base_order_quantity(material_id)

    base_lead = supplier.base_lead_time_days
    if random.random() <= supplier.historical_on_time_rate:
        delay = random.randint(-1, 1)
    else:
        delay = random.randint(2, 7)

    actual_lead = max(2, base_lead + delay + extra_delay)
    expected_date = current_day + timedelta(days=base_lead)
    receipt_date = current_day + timedelta(days=actual_lead)

    new_po = PurchaseOrder(
        id=next_po_id, supplier_id=supplier_id, order_date=current_day,
        expected_delivery_date=expected_date, status="Pending",
    )
    db.add(new_po)
    db.flush()
    next_po_id += 1

    new_po_line = PurchaseOrderLine(
        id=next_po_line_id, po_id=new_po.id, material_id=material_id,
        quantity_ordered=order_qty, quantity_received=0,
    )
    db.add(new_po_line)
    db.flush()
    next_po_line_id += 1

    open_purchase_orders.append({
        "po": new_po, "material_id": material_id,
        "remaining_qty": order_qty, "receipt_date": receipt_date,
        "forced_fraction": forced_fraction,
    })

    stats["purchase_orders"] += 1
    stats["purchase_units_ordered"] += order_qty

    tag = "[INCIDENT-FORCED] " if is_forced else ""
    log(f"{current_day}: {tag}PO {new_po.id} placed for material {material_id}; "
        f"supplier={supplier_id}; qty={order_qty}; expected={expected_date}; "
        f"actual_receipt={receipt_date}")

    return new_po


def apply_incident_to_material(material_id, supplier_id, extra_delay, forced_fraction, current_day):
    """Route an active supply-side incident onto a real transaction:
    extend an existing open PO if one exists for this material,
    otherwise force a new one into existence."""
    existing = next((po_info for po_info in open_purchase_orders
                      if po_info["material_id"] == material_id), None)

    if existing:
        if extra_delay > 0:
            existing["receipt_date"] = existing["receipt_date"] + timedelta(days=extra_delay)
        if forced_fraction is not None:
            existing["forced_fraction"] = forced_fraction
        log(f"{current_day}: [INCIDENT] extended existing PO {existing['po'].id} "
            f"(material {material_id}) -> new receipt {existing['receipt_date']} "
            f"due to supplier {supplier_id} disruption")
        return

    place_new_po(material_id, current_day, forced_supplier_id=supplier_id,
                 extra_delay=extra_delay, forced_fraction=forced_fraction, is_forced=True)


# ============================================================
# HEADER
# ============================================================

print("=" * 70)
print("SAGE ROBUST NORMAL BASELINE SIMULATION")
print("=" * 70)
print(f"Customers available : {len(customers)}")
print(f"Inventory items     : {len(inventory_items)}")
print(f"Suppliers           : {len(suppliers)}")
print(f"Simulation period   : {START_DATE} -> {END_DATE}")
print(f"Random seed         : {SEED}")
print("=" * 70)

if INCIDENTS_ENABLED:
    print("\nINCIDENTS SCHEDULED THIS RUN")
    print("-" * 70)
    for inc in incidents:
        print(f"  {inc['id']:8} {inc['type']:38} {inc['start_date']} -> {inc['end_date']}")
    print("-" * 70)


# ============================================================
# MAIN SIMULATION
# ============================================================

current_day = START_DATE

while current_day <= END_DATE:

    for po_info in list(open_purchase_orders):

        if current_day < po_info["receipt_date"]:
            continue

        po = po_info["po"]
        material_id = po_info["material_id"]
        ordered_qty = po_info["remaining_qty"]

        if ordered_qty <= 0:
            open_purchase_orders.remove(po_info)
            continue

        if po_info.get("forced_fraction") is not None:
            # A partial_receipt incident was active on the day this PO
            # was placed -- force this first receipt to that fraction,
            # then clear it so later top-up receipts on the same PO
            # behave normally.
            receipt_qty = max(1, int(ordered_qty * po_info["forced_fraction"]))
            po_info["forced_fraction"] = None
        elif ordered_qty > 300 and random.random() < 0.25:
            receipt_qty = int(ordered_qty * random.uniform(0.55, 0.80))
        else:
            receipt_qty = ordered_qty
        receipt_qty = max(1, min(receipt_qty, ordered_qty))

        new_receipt = GoodsReceipt(
            id=next_receipt_id, po_id=po.id, receipt_date=current_day,
            status="Complete" if receipt_qty == ordered_qty else "Partial",
        )
        db.add(new_receipt)
        db.flush()
        next_receipt_id += 1

        po_line = db.query(PurchaseOrderLine).filter_by(po_id=po.id).first()
        if po_line is None:
            raise RuntimeError(f"No purchase order line found for PO {po.id}.")

        already_received = po_line.quantity_received or 0
        po_line.quantity_received = already_received + receipt_qty

        new_receipt_line = GoodsReceiptLine(
            id=next_receipt_line_id, receipt_id=new_receipt.id,
            po_line_id=po_line.id, material_id=material_id,
            quantity_received=receipt_qty,
        )
        db.add(new_receipt_line)
        db.flush()
        next_receipt_line_id += 1

        item = item_by_product[material_id]
        new_movement = StockMovement(
            id=next_movement_id, item_id=item.id, date=current_day,
            movement_type="IN", quantity=receipt_qty,
            goods_receipt_line_id=new_receipt_line.id,
        )
        db.add(new_movement)
        db.flush()
        next_movement_id += 1

        change_stock(material_id, receipt_qty)
        po_info["remaining_qty"] -= receipt_qty

        stats["purchase_receipts"] += 1
        stats["purchase_units_received"] += receipt_qty

        log(f"{current_day}: received {receipt_qty} units of material "
            f"{material_id} against PO {po.id}; stock={get_stock(material_id):.0f}")

        if po_info["remaining_qty"] <= 0:
            po.status = "Complete"
            open_purchase_orders.remove(po_info)
        else:
            po_info["receipt_date"] = current_day + timedelta(days=random.randint(2, 5))
            po.status = "Partial"

    for material_id in [101, 102, 103]:
        item = item_by_product[material_id]

        existing_open = any(x["material_id"] == material_id for x in open_purchase_orders)
        if existing_open:
            continue

        stock = get_stock(material_id)

        if stock <= item.reorder_point:
            supplier_id = choose_supplier(material_id)
            extra_delay, forced_fraction = supplier_incident_effect(supplier_id, current_day)
            if extra_delay > 0:
                log(f"{current_day}: incident adding {extra_delay} extra delay day(s) "
                    f"to supplier {supplier_id}'s PO for material {material_id}")

            place_new_po(material_id, current_day, forced_supplier_id=supplier_id,
                         extra_delay=extra_delay, forced_fraction=forced_fraction)

    # ------------------------------------------------------------
    # INCIDENT-TRIGGERED SUPPLY EVENTS
    # ------------------------------------------------------------
    # Runs once, exactly on the incident's start date -- guarantees
    # the 5 supply-side scenarios always have a real transaction to
    # act on, whether or not the natural reorder-point check above
    # happened to fire for that material this year. See the
    # apply_incident_to_material()/place_new_po() definitions above
    # for the full reasoning.
    for inc in incidents:
        if inc["start_date"] != current_day:
            continue
        if inc["type"] not in SUPPLY_INCIDENT_TYPES:
            continue

        supplier_ids = inc.get("supplier_ids") or (
            [inc["supplier_id"]] if inc.get("supplier_id") is not None else []
        )

        for supplier_id in supplier_ids:
            material_id = material_needing_most_from_supplier(supplier_id)
            if material_id is None:
                continue
            extra_delay, forced_fraction = supplier_incident_effect(supplier_id, current_day)
            apply_incident_to_material(material_id, supplier_id, extra_delay, forced_fraction, current_day)

    if production_day(current_day):
        production_products = [201, 202]
        random.shuffle(production_products)

        for product_id in production_products:
            planned_qty = PRODUCTION_BATCH[product_id]
            max_qty = maximum_producible(product_id, planned_qty)

            capacity_reduction = product_capacity_reduction(product_id, current_day)
            if capacity_reduction > 0:
                max_qty = int(max_qty * (1 - capacity_reduction))
                step = PRODUCTION_STEP[product_id]
                max_qty = (max_qty // step) * step
                log(f"{current_day}: incident reducing product {product_id} capacity by "
                    f"{capacity_reduction:.0%}; max producible now {max_qty}")

            if max_qty > 0 and random.random() < 0.15:
                reduction = random.choice([2, 4, 6])
                actual_qty = max(0, max_qty - reduction)
                step = PRODUCTION_STEP[product_id]
                actual_qty = (actual_qty // step) * step
            else:
                actual_qty = max_qty

            status = "Completed" if actual_qty == planned_qty else "Delayed"

            new_prod = ProductionOrder(
                id=next_prod_id, product_id=product_id,
                planned_start=current_day, planned_end=current_day,
                actual_start=current_day if actual_qty > 0 else None,
                actual_end=current_day if actual_qty > 0 else None,
                planned_qty=planned_qty, actual_qty=actual_qty, status=status,
            )
            db.add(new_prod)
            db.flush()
            next_prod_id += 1

            stats["production_orders"] += 1
            stats["units_planned"] += planned_qty
            stats["units_produced"] += actual_qty
            if status == "Completed":
                stats["production_completed"] += 1
            else:
                stats["production_delayed"] += 1

            if actual_qty > 0:
                requirements = required_materials(product_id, actual_qty)

                for material_id, amount in requirements.items():
                    raw_item = item_by_product[material_id]

                    if get_stock(material_id) < amount:
                        raise RuntimeError(
                            f"Production would create negative stock. "
                            f"material={material_id}, needed={amount}, "
                            f"available={get_stock(material_id)}"
                        )

                    planned_amount = int(round(
                        next(b.quantity_required for b in bom_rows
                             if b.finished_good_id == product_id
                             and b.raw_material_id == material_id) * planned_qty
                    ))

                    new_issue = MaterialIssue(
                        id=next_issue_id, production_order_id=new_prod.id,
                        item_id=raw_item.id, planned_quantity=planned_amount,
                        planned_issue_date=current_day, quantity_issued=amount,
                        issue_date=current_day,
                    )
                    db.add(new_issue)
                    db.flush()
                    next_issue_id += 1

                    new_movement = StockMovement(
                        id=next_movement_id, item_id=raw_item.id, date=current_day,
                        movement_type="OUT", quantity=amount, material_issue_id=new_issue.id,
                    )
                    db.add(new_movement)
                    db.flush()
                    next_movement_id += 1
                    change_stock(material_id, -amount)

                finished_item = item_by_product[product_id]
                fg_movement = StockMovement(
                    id=next_movement_id, item_id=finished_item.id, date=current_day,
                    movement_type="IN", quantity=actual_qty, production_order_id=new_prod.id,
                )
                db.add(fg_movement)
                db.flush()
                next_movement_id += 1
                change_stock(product_id, actual_qty)

            log(f"{current_day}: produced {actual_qty}/{planned_qty} of product "
                f"{product_id} [{status}]")

    if current_day.weekday() < 5 and random.random() < 0.42:
        selected_customers = random.sample(customers, random.randint(1, min(3, len(customers))))

        for customer in selected_customers:
            product_id = random.choice([201, 202])
            demand = customer_demand(customer, product_id, current_day)
            if demand <= 0:
                continue

            requested_delivery_date = current_day + timedelta(days=random.randint(3, 10))

            new_order = SalesOrder(
                id=next_sales_order_id, customer_id=customer.id, order_date=current_day,
                requested_delivery_date=requested_delivery_date, status="Pending",
            )
            db.add(new_order)
            db.flush()
            next_sales_order_id += 1

            new_line = SalesOrderLine(
                id=next_sales_line_id, sales_order_id=new_order.id,
                product_id=product_id, quantity_ordered=demand, quantity_fulfilled=0,
            )
            db.add(new_line)
            db.flush()
            next_sales_line_id += 1

            open_sales_orders.append({
                "order": new_order, "line": new_line, "product_id": product_id,
                "remaining_qty": demand, "requested_delivery_date": requested_delivery_date,
                "order_date": current_day,
            })

            stats["sales_orders"] += 1
            stats["sales_units_ordered"] += demand

            log(f"{current_day}: customer {customer.id} ordered {demand} units "
                f"of product {product_id}")

    for order_info in list(open_sales_orders):
        product_id = order_info["product_id"]
        remaining = order_info["remaining_qty"]

        if remaining <= 0:
            open_sales_orders.remove(order_info)
            continue

        available = int(get_stock(product_id))
        if available <= 0:
            continue

        shipped_qty = min(remaining, available)
        if shipped_qty <= 0:
            continue

        order = order_info["order"]
        line = order_info["line"]

        new_delivery = Delivery(
            id=next_delivery_id, sales_order_id=order.id,
            ship_date=current_day, delivery_date=current_day, status="Complete",
        )
        db.add(new_delivery)
        db.flush()
        next_delivery_id += 1

        new_delivery_line = DeliveryLine(
            id=next_delivery_line_id, delivery_id=new_delivery.id,
            sales_order_line_id=line.id, product_id=product_id,
            quantity_shipped=shipped_qty,
        )
        db.add(new_delivery_line)
        db.flush()
        next_delivery_line_id += 1

        finished_item = item_by_product[product_id]
        delivery_movement = StockMovement(
            id=next_movement_id, item_id=finished_item.id, date=current_day,
            movement_type="OUT", quantity=shipped_qty, delivery_line_id=new_delivery_line.id,
        )
        db.add(delivery_movement)
        db.flush()
        next_movement_id += 1
        change_stock(product_id, -shipped_qty)

        previous_fulfilled = line.quantity_fulfilled or 0
        line.quantity_fulfilled = previous_fulfilled + shipped_qty
        order_info["remaining_qty"] -= shipped_qty

        stats["sales_units_fulfilled"] += shipped_qty
        stats["deliveries"] += 1
        stats["delivery_units"] += shipped_qty

        if order_info["remaining_qty"] <= 0:
            order.status = "Complete"
            open_sales_orders.remove(order_info)
        else:
            order.status = "Partial"

        log(f"{current_day}: delivered {shipped_qty} units of product {product_id} "
            f"for sales order {order.id}; remaining={order_info['remaining_qty']}")

    for order_info in open_sales_orders:
        order = order_info["order"]
        if (current_day - order_info["order_date"]).days > 14:
            order.status = "Backorder"

    current_day += timedelta(days=1)


# ============================================================
# FLUSH EVERYTHING BEFORE VALIDATION
# ============================================================

db.flush()


# ============================================================
# FINALISE OPEN ORDERS
# ============================================================

for order_info in open_sales_orders:
    order = order_info["order"]
    if order_info["remaining_qty"] > 0:
        order.status = "Backorder"
        stats["sales_units_backordered"] += order_info["remaining_qty"]


# ============================================================
# RECONCILIATION
# ============================================================

print()
print("=" * 70)
print("VALIDATION")
print("=" * 70)

validation_passed = True

for item in inventory_items:
    total_in = sum(
        m.quantity for m in db.query(StockMovement)
        .filter_by(item_id=item.id, movement_type="IN").all()
    )
    total_out = sum(
        m.quantity for m in db.query(StockMovement)
        .filter_by(item_id=item.id, movement_type="OUT").all()
    )
    expected = item.opening_balance_qty + total_in - total_out
    actual = current_stock[item.id]

    if abs(expected - actual) > 0.01:
        print(f"INVENTORY RECONCILIATION: FAIL (item {item.id}: "
              f"expected {expected}, actual {actual})")
        validation_passed = False
    else:
        print(f"INVENTORY RECONCILIATION (item {item.id}): PASS "
              f"(ending stock {actual:.0f})")

total_sales_ordered = sum(l.quantity_ordered for l in db.query(SalesOrderLine).all())
total_sales_fulfilled = sum(l.quantity_fulfilled or 0 for l in db.query(SalesOrderLine).all())
if total_sales_ordered != stats["sales_units_ordered"] or total_sales_fulfilled != stats["sales_units_fulfilled"]:
    print("SALES RECONCILIATION: FAIL")
    validation_passed = False
else:
    print("SALES RECONCILIATION: PASS")

total_po_received = sum(l.quantity_received or 0 for l in db.query(PurchaseOrderLine).all())
if total_po_received != stats["purchase_units_received"]:
    print("PURCHASE RECONCILIATION: FAIL")
    validation_passed = False
else:
    print("PURCHASE RECONCILIATION: PASS")

print("=" * 70)
if not validation_passed:
    raise RuntimeError("Validation failed -- see FAIL lines above. Data was NOT committed.")
print("ALL VALIDATION CHECKS PASSED")
print("=" * 70)


# ============================================================
# COMMIT
# ============================================================

db.commit()

print()
print("=" * 70)
print("BASELINE SIMULATION FINISHED")
print("=" * 70)
print()
print("FINAL INVENTORY")
for item in inventory_items:
    product = products[item.product_id]
    print(f"Item {item.id} ({product.name}, product {item.product_id}): "
          f"{current_stock[item.id]:.0f}")

print()
print("=" * 70)
print("SIMULATION SUMMARY")
print("=" * 70)
print(f"Production orders       : {stats['production_orders']}")
print(f"Completed production    : {stats['production_completed']}")
print(f"Delayed production      : {stats['production_delayed']}")
print(f"Units planned           : {stats['units_planned']}")
print(f"Units produced          : {stats['units_produced']}")
print(f"Purchase orders         : {stats['purchase_orders']}")
print(f"Purchase receipts       : {stats['purchase_receipts']}")
print(f"Units ordered           : {stats['purchase_units_ordered']}")
print(f"Units received          : {stats['purchase_units_received']}")
print(f"Sales orders            : {stats['sales_orders']}")
print(f"Sales units ordered     : {stats['sales_units_ordered']}")
print(f"Sales units backordered : {stats['sales_units_backordered']}")
print(f"Deliveries              : {stats['deliveries']}")
print(f"Delivery units          : {stats['delivery_units']}")
print()
print("=" * 70)

db.close()