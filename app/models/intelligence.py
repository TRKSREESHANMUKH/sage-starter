from sqlalchemy import Column, Integer, String, Float, Date, Text, ForeignKey
from app.database import Base


class BusinessEvent(Base):
    __tablename__ = "business_events"

    id = Column(Integer, primary_key=True)
    event_type = Column(String(30), nullable=False)
    entity_type = Column(String(30), nullable=False)
    entity_id = Column(Integer, nullable=False)
    occurred_start_date = Column(Date, nullable=False)
    occurred_end_date = Column(Date, nullable=True)
    metric_name = Column(String(50), nullable=False)
    metric_value = Column(Float, nullable=False)
    metric_unit = Column(String(20), nullable=False)
    baseline_value = Column(Float, nullable=True)
    threshold_value = Column(Float, nullable=True)
    status = Column(String(20), nullable=False)
    description = Column(Text, nullable=True)

class Risk(Base):
    __tablename__ = "risks"

    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("business_events.id"), nullable=False)
    assessed_at = Column(Date, nullable=False)
    risk_score = Column(Float, nullable=False)
    severity = Column(String(10), nullable=False)
    affected_order_count = Column(Integer, nullable=True)
    impact_description = Column(Text, nullable=True)
    priority_rank = Column(Integer, nullable=False)

class CausalAnalysisRun(Base):
    __tablename__ = "causal_analysis_runs"

    id = Column(Integer, primary_key=True)
    analysis_date = Column(Date, nullable=False)
    dag_version = Column(String(20), nullable=False)
    baseline_window_start = Column(Date, nullable=False)
    baseline_window_end = Column(Date, nullable=False)
    comparison_window_start = Column(Date, nullable=False)
    comparison_window_end = Column(Date, nullable=False)
    random_seed = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)


class CausalAttribution(Base):
    __tablename__ = "causal_attributions"

    id = Column(Integer, primary_key=True)
    analysis_run_id = Column(Integer, ForeignKey("causal_analysis_runs.id"), nullable=False)
    effect_event_id = Column(Integer, ForeignKey("business_events.id"), nullable=False)
    candidate_node = Column(String(50), nullable=False)
    candidate_event_id = Column(Integer, ForeignKey("business_events.id"), nullable=True)
    attribution_score = Column(Float, nullable=False)
    attribution_rank = Column(Integer, nullable=False)
    path_nodes = Column(Text, nullable=True)  # JSON stored as text