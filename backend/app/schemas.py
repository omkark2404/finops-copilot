from __future__ import annotations
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Any
from enum import Enum
from datetime import datetime, date
import uuid

# --- Enums ---
class FocusVersion(str, Enum):
    v1_0 = "1.0"
    v1_0_1 = "1.0.1"
    unknown = "unknown"

class IngestionStatus(str, Enum):
    queued = "QUEUED"
    running = "RUNNING"
    succeeded = "SUCCEEDED"
    failed = "FAILED"
    cancelled = "CANCELLED"

class QualityStatus(str, Enum):
    pass_ = "PASS"
    warn = "WARN"
    fail = "FAIL"

class AnomalyMethod(str, Enum):
    rolling_zscore = "rolling_zscore"
    ewma = "ewma"
    robust_zscore = "robust_zscore"
    seasonal = "seasonal"
    isolation_forest = "isolation_forest"

class AnomalySeverity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"

class AnomalyStatus(str, Enum):
    open = "open"
    investigating = "investigating"
    resolved = "resolved"
    dismissed = "dismissed"

class OpportunityType(str, Enum):
    cost_growth = "cost_growth"
    cost_spike = "cost_spike"
    cost_concentration = "cost_concentration"
    commitment_candidate = "commitment_candidate"
    regional_pricing = "regional_pricing"
    quantity_growth = "quantity_growth"
    idle_candidate = "idle_candidate"

class RecommendationStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    simulated = "simulated"

class ScenarioType(str, Enum):
    usage_reduction = "usage_reduction"
    price_change = "price_change"
    budget_reduction = "budget_reduction"
    recommendation_implementation = "recommendation_implementation"

class ForecastMethod(str, Enum):
    naive = "naive"
    moving_average = "moving_average"
    exp_smoothing = "exp_smoothing"
    lightgbm = "lightgbm"

class AgentStatus(str, Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    skipped = "skipped"

class AgentType(str, Enum):
    data_quality = "data_quality"
    cost_attribution = "cost_attribution"
    anomaly_investigation = "anomaly_investigation"
    opportunity = "opportunity"
    optimization = "optimization"
    savings = "savings"
    critic = "critic"

class UserRole(str, Enum):
    admin = "ADMIN"
    finops_analyst = "FINOPS_ANALYST"
    engineering_manager = "ENGINEERING_MANAGER"
    executive = "EXECUTIVE"
    viewer = "VIEWER"

class DecisionOutcome(str, Enum):
    approve = "APPROVE"
    reject = "REJECT"
    escalate = "ESCALATE"
    investigate = "INVESTIGATE"

# --- Dataset / Ingestion ---
class DatasetInfo(BaseModel):
    id: str
    name: str
    source: str
    focus_version: FocusVersion
    row_count: int
    date_range_start: Optional[date]
    date_range_end: Optional[date]
    currency: Optional[str]
    ingested_at: datetime
    validation_status: QualityStatus
    content_hash: str
    is_demo: bool = False
    source_url: Optional[str] = None

class IngestionRequest(BaseModel):
    dataset_name: str
    description: Optional[str] = None
    source_url: Optional[str] = None

# --- Data Quality ---
class FieldQualityMetric(BaseModel):
    field_name: str
    null_rate: float
    unique_count: int
    invalid_count: int
    sample_invalids: list[str] = []

class DataQualityReport(BaseModel):
    dataset_id: str
    overall_status: QualityStatus
    total_rows: int
    valid_rows: int
    duplicate_rows: int
    null_rate_by_field: dict[str, float]
    field_metrics: list[FieldQualityMetric]
    currency_consistency: bool
    date_range_valid: bool
    issues: list[str]
    warnings: list[str]
    generated_at: datetime

# --- Analytics ---
class SpendDataPoint(BaseModel):
    date: str  # ISO date string
    billed_cost: float
    effective_cost: float

class SpendTrend(BaseModel):
    granularity: str
    period_start: str
    period_end: str
    data_points: list[SpendDataPoint]

class SpendSummary(BaseModel):
    period_start: str
    period_end: str
    total_billed_cost: float
    total_effective_cost: float
    currency: str
    mom_change_pct: Optional[float] = None
    provider_breakdown: dict[str, float]
    account_breakdown: dict[str, float]
    service_breakdown: dict[str, float]
    region_breakdown: dict[str, float]

class CostDriver(BaseModel):
    dimension: str
    value: str
    cost: float
    share_pct: float
    change_pct: Optional[float] = None

class CostAttributionReport(BaseModel):
    dataset_id: str
    period_start: str
    period_end: str
    top_drivers: list[CostDriver]
    total_cost: float
    concentration_score: float  # HHI 0-1
    period_over_period_change_pct: Optional[float]
    evidence: list[str]

# --- Anomaly ---
class AnomalyDetail(BaseModel):
    id: str
    dataset_id: str
    entity_type: str
    entity_value: str
    detected_at: str
    actual_cost: float
    expected_cost: float
    deviation: float
    deviation_pct: float
    severity: AnomalySeverity
    method: AnomalyMethod
    confidence: float  # 0-1
    supporting_evidence: list[str]
    status: AnomalyStatus = AnomalyStatus.open

class AnomalyReport(BaseModel):
    dataset_id: str
    period_start: str
    period_end: str
    anomalies: list[AnomalyDetail]
    total_anomalies: int
    critical_count: int
    high_count: int

# --- Opportunity & Optimization ---
class Opportunity(BaseModel):
    id: str
    dataset_id: str
    opportunity_type: OpportunityType
    entity: str
    description: str
    evidence: list[str]
    potential_savings_estimate: float
    confidence: float
    priority_score: float

class OpportunityReport(BaseModel):
    dataset_id: str
    opportunities: list[Opportunity]
    total_opportunities: int
    total_potential_savings: float

class OptimizationAction(BaseModel):
    action_type: str
    description: str
    rationale: str
    assumptions: list[str]
    confidence: float

class OptimizationRecommendation(BaseModel):
    id: str
    opportunity_id: str
    dataset_id: str
    title: str
    description: str
    actions: list[OptimizationAction]
    priority_rank: int
    risk_level: str  # low / medium / high
    evidence: list[str]
    status: RecommendationStatus
    explanation: Optional[str] = None  # LLM-generated text only

# --- Savings ---
class SavingsEstimate(BaseModel):
    recommendation_id: str
    scenario_type: ScenarioType
    scenario_description: str
    current_cost: float
    projected_cost: float
    estimated_savings: float  # ESTIMATED, NOT REALIZED
    estimated_savings_pct: float
    assumptions: list[str]
    confidence: float
    time_horizon_days: int
    created_at: datetime
    # NOTE: This is always ESTIMATED savings, never REALIZED savings

# --- Forecast ---
class ForecastPoint(BaseModel):
    date: str
    predicted_cost: float
    lower_bound: Optional[float] = None
    upper_bound: Optional[float] = None

class ForecastResult(BaseModel):
    entity: str
    method: ForecastMethod
    forecast_horizon_days: int
    points: list[ForecastPoint]
    metrics: dict[str, float]  # mae, rmse, wape, bias
    training_period: dict[str, str]
    model_version: str
    generated_at: datetime
    baseline_metrics: Optional[dict[str, float]] = None  # naive baseline for comparison

# --- Agent Pipeline ---
class AgentRunDetail(BaseModel):
    id: str
    pipeline_run_id: str
    agent_type: AgentType
    status: AgentStatus
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_seconds: Optional[float]
    input_summary: dict[str, Any]
    output_summary: dict[str, Any]
    confidence: Optional[float]
    error_message: Optional[str]
    retry_count: int = 0

class ValidationReport(BaseModel):
    checks_passed: list[str]
    checks_failed: list[str]
    contradictions: list[str]
    missing_evidence: list[str]
    unsupported_claims: list[str]
    recommendation_safe: bool
    confidence: float

class FinalDecision(BaseModel):
    pipeline_run_id: str
    recommendation_id: Optional[str]
    decision: DecisionOutcome
    rationale: str
    evidence_summary: list[str]
    confidence: float
    validated_by_critic: bool
    human_action: Optional[str] = None  # None / approved / rejected
    created_at: datetime

class PipelineRunDetail(BaseModel):
    id: str
    dataset_id: str
    status: AgentStatus
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    agent_runs: list[AgentRunDetail]
    final_decision: Optional[FinalDecision]

# --- Auth ---
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    email: Optional[str] = None
    role: Optional[UserRole] = None

class UserCreate(BaseModel):
    email: str
    password: str
    role: UserRole = UserRole.viewer

class UserResponse(BaseModel):
    id: str
    email: str
    role: UserRole
    is_active: bool
    created_at: datetime

class LoginRequest(BaseModel):
    email: str
    password: str

# --- API ---
class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None

class JobResponse(BaseModel):
    job_id: str
    status: IngestionStatus
    message: str

class HealthResponse(BaseModel):
    status: str
    database: str
    cache: str
    version: str
    llm_available: bool
    llm_provider: str

class BudgetCreate(BaseModel):
    name: str
    entity_type: str
    entity_value: str
    period_type: str
    period_start: date
    period_end: date
    budget_amount: float
    currency: str = "USD"

class BudgetSummary(BaseModel):
    id: str
    name: str
    entity_type: str
    entity_value: str
    period_start: date
    period_end: date
    budget_amount: float
    actual_spend: Optional[float]
    variance: Optional[float]
    variance_pct: Optional[float]
    status: str  # on_track / at_risk / over_budget
    currency: str
