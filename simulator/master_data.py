from datetime import date
from sqlalchemy import text
from app.database import SessionLocal
from app.models.suppliers import Supplier
from app.models.inventory import Product, InventoryItem, BillOfMaterials
from app.models.sales import Customer

def seed_master_data():
    db = SessionLocal()

    # Truncate all transactional, intelligence, and master tables safely with CASCADE
    db.execute(text(
        "TRUNCATE purchase_orders, purchase_order_lines, goods_receipts, goods_receipt_lines, "
        "production_orders, material_issues, stock_movements, sales_orders, sales_order_lines, "
        "deliveries, delivery_lines, bill_of_materials, inventory_items, products, suppliers, customers, "
        "business_events, risks, causal_analysis_runs, causal_attributions "
        "RESTART IDENTITY CASCADE;"
    ))
    db.commit()


    suppliers = [
        Supplier(id=1, name="Sri Materials Pvt Ltd", region="South India",
                  base_lead_time_days=7, historical_on_time_rate=0.92),
        Supplier(id=2, name="Bharat Steel Works", region="North India",
                  base_lead_time_days=10, historical_on_time_rate=0.85),
        Supplier(id=3, name="Global Polymers Co", region="West India",
                  base_lead_time_days=14, historical_on_time_rate=0.78),
        Supplier(id=4, name="EastCoast Components", region="East India",
                  base_lead_time_days=9, historical_on_time_rate=0.88),
        Supplier(id=5, name="Copper & Co", region="South India",
                  base_lead_time_days=12, historical_on_time_rate=0.81),
    ]
    db.add_all(suppliers)

    products = [
        Product(id=101, name="Steel Rod 10mm", category="Raw Material", unit_of_measure="kg"),
        Product(id=102, name="Plastic Granules", category="Raw Material", unit_of_measure="kg"),
        Product(id=103, name="Copper Wire", category="Raw Material", unit_of_measure="meters"),
        Product(id=201, name="Widget Model X", category="Finished Good", unit_of_measure="units"),
        Product(id=202, name="Widget Model Y", category="Finished Good", unit_of_measure="units"),
    ]
    db.add_all(products)
    db.flush()

    # LEAN INITIAL BALANCES & REORDER POINTS:
    # Tuned so inventory cycles naturally, allowing supplier delay incidents
    # (like INC_09) to reliably deplete stock and produce genuine backorders.
    inventory_items = [
        InventoryItem(id=1, product_id=101, safety_stock=100, reorder_point=200,
                      opening_balance_qty=300, opening_balance_date=date(2025, 1, 1)),
        InventoryItem(id=2, product_id=102, safety_stock=50, reorder_point=120,
                      opening_balance_qty=250, opening_balance_date=date(2025, 1, 1)),
        InventoryItem(id=3, product_id=103, safety_stock=30, reorder_point=80,
                      opening_balance_qty=180, opening_balance_date=date(2025, 1, 1)),
        InventoryItem(id=4, product_id=201, safety_stock=40, reorder_point=80,
                      opening_balance_qty=100, opening_balance_date=date(2025, 1, 1)),
        InventoryItem(id=5, product_id=202, safety_stock=40, reorder_point=80,
                      opening_balance_qty=100, opening_balance_date=date(2025, 1, 1)),
    ]
    db.add_all(inventory_items)
    db.flush()

    bom = [
        BillOfMaterials(id=1, finished_good_id=201, raw_material_id=101, quantity_required=2.5),
        BillOfMaterials(id=2, finished_good_id=201, raw_material_id=102, quantity_required=1.0),
        BillOfMaterials(id=3, finished_good_id=202, raw_material_id=103, quantity_required=0.5),
        BillOfMaterials(id=4, finished_good_id=202, raw_material_id=101, quantity_required=1.2),
        BillOfMaterials(id=5, finished_good_id=201, raw_material_id=103, quantity_required=0.3),
    ]
    db.add_all(bom)

    customers = [
        Customer(id=1, name="Nova Retailers", region="South India"),
        Customer(id=2, name="Metro Distributors", region="North India"),
        Customer(id=3, name="Coastal Traders", region="West India"),
        Customer(id=4, name="Prime Retail Group", region="East India"),
        Customer(id=5, name="Sunrise Wholesalers", region="South India"),
    ]
    db.add_all(customers)

    db.commit()
    print("Master data inserted successfully!")
    db.close()

if __name__ == "__main__":
    seed_master_data()