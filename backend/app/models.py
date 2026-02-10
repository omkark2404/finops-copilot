from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean, Column, DateTime, Float, Integer, String, Text,
    ForeignKey, JSON, Enum as SAEnum, func
)
from sqlalchemy.orm import relationship, Mapped, mapped_column

from .db import Base
from .schemas import UserRole, QualityStatus, AnomalySeverity, AnomalyMethod, AnomalyStatus, IngestionStatus, RecommendationStatus, AgentType, AgentStatus


def gen_uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False, default=UserRole.viewer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class Dataset(Base):
    __tablename__ = "datasets"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    source_url: Mapped[Optional[str]] = mapped_column(String)
    source_provider: Mapped[Optional[str]] = mapped_column(String)
    focus_version: Mapped[Optional[str]] = mapped_column(String)
    file_path: Mapped[Optional[str]] = mapped_column(String)
    parquet_path: Mapped[Optional[str]] = mapped_column(String)
    row_count: Mapped[Optional[int]] = mapped_column(Integer)
    date_range_start: Mapped[Optional[datetime]] = mapped_column(DateTime)
    date_range_end: Mapped[Optional[datetime]] = mapped_column(DateTime)
    currency: Mapped[Optional[str]] = mapped_column(String(10))
    content_hash: Mapped[Optional[str]] = mapped_column(String(64))
    download_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime)
    ingested_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    validation_status: Mapped[Optional[str]] = mapped_column(String, default="PENDING")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[Optional[str]] = mapped_column(String, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    dataset_id: Mapped[str] = mapped_column(String, ForeignKey("datasets.id"), nullable=False)
    status: Mapped[str] = mapped_column(String, default=IngestionStatus.queued)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    rows_processed: Mapped[Optional[int]] = mapped_column(Integer)
    rows_valid: Mapped[Optional[int]] = mapped_column(Integer)
    rows_invalid: Mapped[Optional[int]] = mapped_column(Integer)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class DataQualityReportModel(Base):
    __tablename__ = "data_quality_reports"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    dataset_id: Mapped[str] = mapped_column(String, ForeignKey("datasets.id"), nullable=False)
    overall_status: Mapped[str] = mapped_column(String)
    total_rows: Mapped[int] = mapped_column(Integer)
    valid_rows: Mapped[int] = mapped_column(Integer)
    duplicate_rows: Mapped[int] = mapped_column(Integer)
    quality_data: Mapped[Optional[dict]] = mapped_column(JSON)
    issues: Mapped[Optional[list]] = mapped_column(JSON)
    warnings: Mapped[Optional[list]] = mapped_column(JSON)
    generated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AnomalyModel(Base):
    __tablename__ = "anomalies"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    dataset_id: Mapped[str] = mapped_column(String, ForeignKey("datasets.id"), nullable=False)
    entity_type: Mapped[str] = mapped_column(String)
    entity_value: Mapped[str] = mapped_column(String)
    detected_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    actual_cost: Mapped[float] = mapped_column(Float)
    expected_cost: Mapped[float] = mapped_column(Float)
    deviation_pct: Mapped[float] = mapped_column(Float)
    severity: Mapped[str] = mapped_column(String)
    method: Mapped[str] = mapped_column(String)
    confidence: Mapped[float] = mapped_column(Float)
    supporting_evidence: Mapped[Optional[list]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String, default=AnomalyStatus.open)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class Investigation(Base):
    __tablename__ = "investigations"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    anomaly_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("anomalies.id"))
    title: Mapped[str] = mapped_column(String)
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, default="open")
    pipeline_run_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("pipeline_runs.id"))
    created_by: Mapped[Optional[str]] = mapped_column(String, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class OpportunityModel(Base):
    __tablename__ = "opportunities"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    dataset_id: Mapped[str] = mapped_column(String, ForeignKey("datasets.id"))
    opportunity_type: Mapped[str] = mapped_column(String)
    entity: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text)
    evidence: Mapped[Optional[list]] = mapped_column(JSON)
    potential_savings_estimate: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float)
    priority_score: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class RecommendationModel(Base):
    __tablename__ = "recommendations"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    opportunity_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("opportunities.id"))
    dataset_id: Mapped[str] = mapped_column(String, ForeignKey("datasets.id"))
    pipeline_run_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("pipeline_runs.id"))
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text)
    actions: Mapped[Optional[list]] = mapped_column(JSON)
    priority_rank: Mapped[int] = mapped_column(Integer, default=1)
    risk_level: Mapped[str] = mapped_column(String, default="medium")
    evidence: Mapped[Optional[list]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String, default=RecommendationStatus.pending)
    approved_by: Mapped[Optional[str]] = mapped_column(String, ForeignKey("users.id"))
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text)
    explanation: Mapped[Optional[str]] = mapped_column(Text)  # LLM-generated text only
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class SavingsEstimateModel(Base):
    __tablename__ = "savings_estimates"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    recommendation_id: Mapped[str] = mapped_column(String, ForeignKey("recommendations.id"))
    scenario_type: Mapped[str] = mapped_column(String)
    scenario_config: Mapped[Optional[dict]] = mapped_column(JSON)
    current_cost: Mapped[float] = mapped_column(Float)
    projected_cost: Mapped[float] = mapped_column(Float)
    estimated_savings: Mapped[float] = mapped_column(Float)  # ESTIMATED, NOT REALIZED
    estimated_savings_pct: Mapped[float] = mapped_column(Float)
    assumptions: Mapped[Optional[list]] = mapped_column(JSON)
    confidence: Mapped[float] = mapped_column(Float)
    time_horizon_days: Mapped[int] = mapped_column(Integer, default=30)
    is_realized: Mapped[bool] = mapped_column(Boolean, default=False)  # Always False in MVP
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ForecastModel(Base):
    __tablename__ = "forecasts"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    dataset_id: Mapped[str] = mapped_column(String, ForeignKey("datasets.id"))
    entity: Mapped[str] = mapped_column(String)
    method: Mapped[str] = mapped_column(String)
    forecast_horizon_days: Mapped[int] = mapped_column(Integer)
    forecast_data: Mapped[Optional[dict]] = mapped_column(JSON)
    metrics: Mapped[Optional[dict]] = mapped_column(JSON)
    training_period: Mapped[Optional[dict]] = mapped_column(JSON)
    model_version: Mapped[str] = mapped_column(String, default="0.1.0")
    model_metadata: Mapped[Optional[dict]] = mapped_column(JSON)
    generated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Budget(Base):
    __tablename__ = "budgets"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    name: Mapped[str] = mapped_column(String)
    entity_type: Mapped[str] = mapped_column(String)
    entity_value: Mapped[str] = mapped_column(String)
    period_type: Mapped[str] = mapped_column(String)  # monthly / quarterly / annual
    period_start: Mapped[Optional[datetime]] = mapped_column(DateTime)
    period_end: Mapped[Optional[datetime]] = mapped_column(DateTime)
    budget_amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    created_by: Mapped[Optional[str]] = mapped_column(String, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    dataset_id: Mapped[str] = mapped_column(String, ForeignKey("datasets.id"))
    status: Mapped[str] = mapped_column(String, default=AgentStatus.queued)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    final_decision: Mapped[Optional[dict]] = mapped_column(JSON)
    created_by: Mapped[Optional[str]] = mapped_column(String, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AgentRunModel(Base):
    __tablename__ = "agent_runs"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    pipeline_run_id: Mapped[str] = mapped_column(String, ForeignKey("pipeline_runs.id"))
    agent_type: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default=AgentStatus.queued)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float)
    input_data: Mapped[Optional[dict]] = mapped_column(JSON)
    output_data: Mapped[Optional[dict]] = mapped_column(JSON)
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ScenarioRun(Base):
    __tablename__ = "scenario_runs"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    recommendation_id: Mapped[str] = mapped_column(String, ForeignKey("recommendations.id"))
    scenario_type: Mapped[str] = mapped_column(String)
    scenario_config: Mapped[Optional[dict]] = mapped_column(JSON)
    result: Mapped[Optional[dict]] = mapped_column(JSON)
    created_by: Mapped[Optional[str]] = mapped_column(String, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    user_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String)
    resource_type: Mapped[Optional[str]] = mapped_column(String)
    resource_id: Mapped[Optional[str]] = mapped_column(String)
    details: Mapped[Optional[dict]] = mapped_column(JSON)
    ip_address: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
