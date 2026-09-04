from sqlalchemy import Column, Integer, String, Date, ForeignKey
from app.database import Base


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id = Column(Integer, primary_key=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    order_date = Column(Date, nullable=False)
    expected_delivery_date = Column(Date, nullable=False)
    status = Column(String(20), nullable=False)


class PurchaseOrderLine(Base):
    __tablename__ = "purchase_order_lines"

    id = Column(Integer, primary_key=True)
    po_id = Column(Integer, ForeignKey("purchase_orders.id"), nullable=False)
    material_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity_ordered = Column(Integer, nullable=False)
    quantity_received = Column(Integer, nullable=True)


class GoodsReceipt(Base):
    __tablename__ = "goods_receipts"

    id = Column(Integer, primary_key=True)
    po_id = Column(Integer, ForeignKey("purchase_orders.id"), nullable=False)
    receipt_date = Column(Date, nullable=False)
    status = Column(String(20), nullable=False)


class GoodsReceiptLine(Base):
    __tablename__ = "goods_receipt_lines"

    id = Column(Integer, primary_key=True)
    receipt_id = Column(Integer, ForeignKey("goods_receipts.id"), nullable=False)
    po_line_id = Column(Integer, ForeignKey("purchase_order_lines.id"), nullable=False)
    material_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity_received = Column(Integer, nullable=False)