from sqlalchemy import Column, Integer, String, Float
from app.database import Base


class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    region = Column(String(50), nullable=False)
    base_lead_time_days = Column(Integer, nullable=False)
    historical_on_time_rate = Column(Float, nullable=False)