from sqlalchemy import Column, Integer, String, Date, ForeignKey
from app.database import Base


class ProductionOrder(Base):
    __tablename__ = "production_orders"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    planned_start = Column(Date, nullable=False)
    planned_end = Column(Date, nullable=False)
    actual_start = Column(Date, nullable=True)
    actual_end = Column(Date, nullable=True)
    planned_qty = Column(Integer, nullable=False)
    actual_qty = Column(Integer, nullable=True)
    status = Column(String(20), nullable=False)


class MaterialIssue(Base):
    __tablename__ = "material_issues"

    id = Column(Integer, primary_key=True)
    production_order_id = Column(Integer, ForeignKey("production_orders.id"), nullable=False)
    item_id = Column(Integer, ForeignKey("inventory_items.id"), nullable=False)
    planned_quantity = Column(Integer, nullable=False)
    planned_issue_date = Column(Date, nullable=False)
    quantity_issued = Column(Integer, nullable=True)
    issue_date = Column(Date, nullable=True)