from sqlalchemy import Column, Integer, String, Date, ForeignKey
from app.database import Base


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    region = Column(String(50), nullable=False)


class SalesOrder(Base):
    __tablename__ = "sales_orders"

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    order_date = Column(Date, nullable=False)
    requested_delivery_date = Column(Date, nullable=False)
    status = Column(String(20), nullable=False)


class SalesOrderLine(Base):
    __tablename__ = "sales_order_lines"

    id = Column(Integer, primary_key=True)
    sales_order_id = Column(Integer, ForeignKey("sales_orders.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity_ordered = Column(Integer, nullable=False)
    quantity_fulfilled = Column(Integer, nullable=True)

class Delivery(Base):
    __tablename__ = "deliveries"

    id = Column(Integer, primary_key=True)
    sales_order_id = Column(Integer, ForeignKey("sales_orders.id"), nullable=False)
    ship_date = Column(Date, nullable=False)
    delivery_date = Column(Date, nullable=True)
    status = Column(String(20), nullable=False)


class DeliveryLine(Base):
    __tablename__ = "delivery_lines"

    id = Column(Integer, primary_key=True)
    delivery_id = Column(Integer, ForeignKey("deliveries.id"), nullable=False)
    sales_order_line_id = Column(Integer, ForeignKey("sales_order_lines.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity_shipped = Column(Integer, nullable=False)