from sqlalchemy import (
    Column, Integer, String, Float, Date, ForeignKey,
    UniqueConstraint, CheckConstraint
)
from app.database import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    category = Column(String(30), nullable=False)  # "Raw Material" or "Finished Good"
    unit_of_measure = Column(String(20), nullable=False)


class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    safety_stock = Column(Integer, nullable=False)
    reorder_point = Column(Integer, nullable=False)
    opening_balance_qty = Column(Integer, nullable=False)
    opening_balance_date = Column(Date, nullable=False)

    __table_args__ = (
        UniqueConstraint("product_id", name="uq_inventory_item_product"),
    )


class BillOfMaterials(Base):
    __tablename__ = "bill_of_materials"

    id = Column(Integer, primary_key=True)
    finished_good_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    raw_material_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity_required = Column(Float, nullable=False)

    __table_args__ = (
        UniqueConstraint("finished_good_id", "raw_material_id", name="uq_bom_pair"),
    )


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id = Column(Integer, primary_key=True)
    item_id = Column(Integer, ForeignKey("inventory_items.id"), nullable=False)
    date = Column(Date, nullable=False)
    movement_type = Column(String(3), nullable=False)  # "IN" or "OUT"
    quantity = Column(Integer, nullable=False)

    goods_receipt_line_id = Column(Integer, ForeignKey("goods_receipt_lines.id"), nullable=True)
    material_issue_id = Column(Integer, ForeignKey("material_issues.id"), nullable=True)
    production_order_id = Column(Integer, ForeignKey("production_orders.id"), nullable=True)
    delivery_line_id = Column(Integer, ForeignKey("delivery_lines.id"), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "(CASE WHEN goods_receipt_line_id IS NOT NULL THEN 1 ELSE 0 END) + "
            "(CASE WHEN material_issue_id IS NOT NULL THEN 1 ELSE 0 END) + "
            "(CASE WHEN production_order_id IS NOT NULL THEN 1 ELSE 0 END) + "
            "(CASE WHEN delivery_line_id IS NOT NULL THEN 1 ELSE 0 END) = 1",
            name="ck_stock_movement_exactly_one_source",
        ),
    )