"""
finops-copilot REST API.
All routes return structured responses.
All routes require authentication except /health.
"""
from __future__ import annotations
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .analytics import get_cost_drivers, get_resource_breakdown, get_spend_summary, get_spend_trend
from .anomaly import run_anomaly_detection
from .agents import get_llm_provider, run_pipeline
from .auth import get_current_user, hash_password, create_access_token, log_audit, require_role, verify_password
from .config import get_settings
from .db import get_db
from .forecasting import forecast_total_spend
from .ingestion import ingest_file
from .models import (
    AnomalyModel, AuditLog, Budget, Dataset, DataQualityReportModel,
    IngestionRun, Investigation, OpportunityModel, PipelineRun as PipelineRunModel,
    RecommendationModel, SavingsEstimateModel, ScenarioRun, User
)
from .optimization import run_optimization_analysis
from .scenarios import run_scenario
from .schemas import (
    BudgetCreate, BudgetSummary, DataQualityReport, DatasetInfo,
    ErrorResponse, FinalDecision, HealthResponse, JobResponse,
    LoginRequest, OptimizationRecommendation, QualityStatus,
    RecommendationStatus, ScenarioType, SpendSummary, SpendTrend,
    Token, UserCreate, UserResponse, UserRole
)

router = APIRouter()


# ── Health ────────────────────────────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse, tags=["Health"])
async def health(db: AsyncSession = Depends(get_db)):
    settings = get_settings()
    db_ok = "ok"
    try:
        await db.execute(select(User).limit(1))
    except Exception:
        db_ok = "error"

    import redis.asyncio as aioredis
    cache_ok = "ok"
    try:
        r = aioredis.from_url(settings.redis_url)
        await r.ping()
        await r.aclose()
    except Exception:
        cache_ok = "error"

    llm = get_llm_provider()

    return HealthResponse(
        status="ok",
        database=db_ok,
        cache=cache_ok,
        version=settings.version,
        llm_available=llm.is_available(),
        llm_provider=llm.name,
    )


# ── Auth ──────────────────────────────────────────────────────────────────────

@router.post("/auth/login", response_model=Token, tags=["Auth"])
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=401, detail="Account disabled")
    token = create_access_token({"sub": user.email, "role": user.role})
    return Token(access_token=token)


@router.post("/auth/register", response_model=UserResponse, tags=["Auth"],
             dependencies=[Depends(require_role(UserRole.admin))])
async def register(body: UserCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        id=str(uuid.uuid4()),
        email=body.email,
        hashed_password=hash_password(body.password),
        role=body.role.value,
    )
    db.add(user)
    await db.commit()
    return UserResponse(id=user.id, email=user.email, role=UserRole(user.role),
                        is_active=user.is_active, created_at=user.created_at)


from sqlalchemy import select, update, delete
from .storage import (
    get_uploads_dir, get_dataset_dir, validate_dataset_id,
    verify_dataset_parquet_exists
)

def _handle_analytics_error(e: Exception):
    err_str = str(e)
    if "DATASET_STORAGE_MISSING" in err_str or "Parquet file missing" in err_str or isinstance(e, FileNotFoundError):
        raise HTTPException(
            status_code=404,
            detail="DATASET_STORAGE_MISSING: The dataset metadata exists, but its analytics file is missing. Re-ingestion is required."
        )
    if isinstance(e, ValueError):
        raise HTTPException(status_code=400, detail=err_str)
    raise HTTPException(status_code=500, detail=err_str)


# ── Datasets ──────────────────────────────────────────────────────────────────

@router.post("/datasets/ingest", response_model=dict, tags=["Datasets"])
async def ingest_dataset(
    file: UploadFile = File(...),
    dataset_name: str = Query(...),
    source_url: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    dataset_id = str(uuid.uuid4())

    # Save uploaded file under DATA_DIR/uploads/
    upload_dir = get_uploads_dir()
    suffix = Path(file.filename).suffix if file.filename else ".csv"
    file_path = upload_dir / f"{dataset_id}{suffix}"

    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Create dataset record
    dataset = Dataset(
        id=dataset_id,
        name=dataset_name,
        source_url=source_url,
        file_path=str(file_path),
        validation_status="PENDING",
        created_by=current_user.id,
    )
    db.add(dataset)
    await db.commit()

    # Run ingestion synchronously
    try:
        provenance, dq_report = ingest_file(
            str(file_path), dataset_id, dataset_name, source_url
        )
        # Update dataset
        dataset.row_count = provenance["row_count"]
        dataset.content_hash = provenance["content_hash"]
        dataset.focus_version = provenance.get("focus_version")
        dataset.parquet_path = provenance.get("parquet_path")
        dataset.currency = provenance.get("currency")
        dataset.ingested_at = datetime.utcnow()
        dataset.validation_status = dq_report.overall_status.value

        if provenance.get("date_range_start"):
            dataset.date_range_start = datetime.fromisoformat(provenance["date_range_start"].replace('+00:00', '').rstrip('Z'))
        if provenance.get("date_range_end"):
            dataset.date_range_end = datetime.fromisoformat(provenance["date_range_end"].replace('+00:00', '').rstrip('Z'))

        # Save DQ report
        dq_model = DataQualityReportModel(
            id=str(uuid.uuid4()),
            dataset_id=dataset_id,
            overall_status=dq_report.overall_status.value,
            total_rows=dq_report.total_rows,
            valid_rows=dq_report.valid_rows,
            duplicate_rows=dq_report.duplicate_rows,
            quality_data={"null_rate_by_field": dq_report.null_rate_by_field},
            issues=dq_report.issues,
            warnings=dq_report.warnings,
        )
        db.add(dq_model)
        await db.commit()

        return {
            "dataset_id": dataset_id,
            "dataset_name": dataset_name,
            "status": "succeeded",
            "row_count": provenance["row_count"],
            "validation_status": dq_report.overall_status.value,
            "issues": dq_report.issues,
            "warnings": dq_report.warnings,
        }
    except Exception as e:
        dataset.validation_status = "FAILED"
        await db.commit()
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/datasets", tags=["Datasets"])
async def list_datasets(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(select(Dataset).order_by(Dataset.created_at.desc()))
    datasets = result.scalars().all()
    return [{"id": d.id, "name": d.name, "row_count": d.row_count,
             "validation_status": d.validation_status, "ingested_at": str(d.ingested_at),
             "focus_version": d.focus_version, "currency": d.currency} for d in datasets]


@router.get("/datasets/{dataset_id}", tags=["Datasets"])
async def get_dataset(
    dataset_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        valid_id = validate_dataset_id(dataset_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid dataset ID format")

    result = await db.execute(select(Dataset).where(Dataset.id == valid_id))
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return {"id": dataset.id, "name": dataset.name, "row_count": dataset.row_count,
            "validation_status": dataset.validation_status, "ingested_at": str(dataset.ingested_at),
            "focus_version": dataset.focus_version, "currency": dataset.currency,
            "date_range_start": str(dataset.date_range_start), "date_range_end": str(dataset.date_range_end)}


@router.delete("/datasets/{dataset_id}", tags=["Datasets"])
async def delete_dataset(
    dataset_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Delete a dataset permanently:
    1. Validate dataset_id format safely.
    2. Check dataset existence.
    3. Clean up database relationships in proper dependency order.
    4. Remove local parquet directory and files.
    5. Clean up DuckDB table state.
    """
    try:
        valid_id = validate_dataset_id(dataset_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid dataset ID format")

    result = await db.execute(select(Dataset).where(Dataset.id == valid_id))
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # 1. Clean up recommendation-dependent models
    rec_result = await db.execute(select(RecommendationModel.id).where(RecommendationModel.dataset_id == valid_id))
    rec_ids = rec_result.scalars().all()
    if rec_ids:
        await db.execute(delete(SavingsEstimateModel).where(SavingsEstimateModel.recommendation_id.in_(rec_ids)))
        await db.execute(delete(ScenarioRun).where(ScenarioRun.recommendation_id.in_(rec_ids)))

    # 2. Clean up pipeline run dependent models
    pipe_result = await db.execute(select(PipelineRunModel.id).where(PipelineRunModel.dataset_id == valid_id))
    pipe_ids = pipe_result.scalars().all()
    if pipe_ids:
        await db.execute(delete(Investigation).where(Investigation.pipeline_run_id.in_(pipe_ids)))
        await db.execute(delete(AgentRunModel).where(AgentRunModel.pipeline_run_id.in_(pipe_ids)))

    # 3. Clean up anomaly dependent models
    anom_result = await db.execute(select(AnomalyModel.id).where(AnomalyModel.dataset_id == valid_id))
    anom_ids = anom_result.scalars().all()
    if anom_ids:
        await db.execute(delete(Investigation).where(Investigation.anomaly_id.in_(anom_ids)))

    # 4. Clean up direct dataset models
    await db.execute(delete(RecommendationModel).where(RecommendationModel.dataset_id == valid_id))
    await db.execute(delete(OpportunityModel).where(OpportunityModel.dataset_id == valid_id))
    await db.execute(delete(PipelineRunModel).where(PipelineRunModel.dataset_id == valid_id))
    await db.execute(delete(AnomalyModel).where(AnomalyModel.dataset_id == valid_id))
    await db.execute(delete(ForecastModel).where(ForecastModel.dataset_id == valid_id))
    await db.execute(delete(DataQualityReportModel).where(DataQualityReportModel.dataset_id == valid_id))
    await db.execute(delete(IngestionRun).where(IngestionRun.dataset_id == valid_id))
    await db.execute(delete(Dataset).where(Dataset.id == valid_id))

    await db.commit()

    # 5. Remove storage objects (R2 objects or local directory + raw upload)
    try:
        from .storage import delete_dataset_storage
        delete_dataset_storage(valid_id)
    except Exception:
        pass

    # 6. Drop DuckDB table if present
    try:
        from .db import get_duck
        duck = get_duck()
        table_name = f"dataset_{valid_id.replace('-', '_')}"
        duck.execute(f"DROP TABLE IF EXISTS {table_name}")
    except Exception:
        pass

    return {"status": "success", "message": f"Dataset {valid_id} deleted successfully"}


# ── Spend Analytics ───────────────────────────────────────────────────────────

@router.get("/spend/summary", response_model=SpendSummary, tags=["Spend"])
async def spend_summary(
    dataset_id: str = Query(...),
    period_start: Optional[str] = Query(None),
    period_end: Optional[str] = Query(None),
    current_user=Depends(get_current_user),
):
    try:
        return get_spend_summary(dataset_id, period_start, period_end)
    except Exception as e:
        _handle_analytics_error(e)


@router.get("/spend/trend", response_model=SpendTrend, tags=["Spend"])
async def spend_trend(
    dataset_id: str = Query(...),
    granularity: str = Query("daily"),
    period_start: Optional[str] = Query(None),
    period_end: Optional[str] = Query(None),
    current_user=Depends(get_current_user),
):
    try:
        return get_spend_trend(dataset_id, granularity, period_start, period_end)
    except Exception as e:
        _handle_analytics_error(e)


@router.get("/spend/breakdown", tags=["Spend"])
async def spend_breakdown(
    dataset_id: str = Query(...),
    dimension: str = Query("service"),
    period_start: Optional[str] = Query(None),
    period_end: Optional[str] = Query(None),
    limit: int = Query(25),
    current_user=Depends(get_current_user),
):
    try:
        return get_resource_breakdown(dataset_id, dimension, period_start, period_end, limit)
    except Exception as e:
        _handle_analytics_error(e)


# ── Anomalies ─────────────────────────────────────────────────────────────────

@router.get("/anomalies", tags=["Anomalies"])
async def list_anomalies(
    dataset_id: str = Query(...),
    entity_type: str = Query("service"),
    current_user=Depends(get_current_user),
):
    try:
        report = run_anomaly_detection(dataset_id, entity_type)
        return report.model_dump()
    except Exception as e:
        _handle_analytics_error(e)


# ── Agent Pipeline ────────────────────────────────────────────────────────────

@router.post("/agent-runs", tags=["Agents"])
async def trigger_pipeline(
    dataset_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        llm = get_llm_provider()
        result = await run_pipeline(dataset_id, llm)
        return result.model_dump()
    except Exception as e:
        _handle_analytics_error(e)


# ── Forecasts ─────────────────────────────────────────────────────────────────

@router.get("/forecasts", tags=["Forecasts"])
async def get_forecasts(
    dataset_id: str = Query(...),
    horizon_days: int = Query(30),
    current_user=Depends(get_current_user),
):
    try:
        result = forecast_total_spend(dataset_id, horizon_days)
        return result.model_dump()
    except Exception as e:
        _handle_analytics_error(e)


# ── Opportunities & Recommendations ───────────────────────────────────────────

@router.get("/opportunities", tags=["Opportunities"])
async def get_opportunities(
    dataset_id: str = Query(...),
    current_user=Depends(get_current_user),
):
    try:
        attribution = get_cost_drivers(dataset_id)
        anomaly_report = run_anomaly_detection(dataset_id)
        report = run_optimization_analysis(dataset_id, attribution, anomaly_report.anomalies)
        return report.model_dump()
    except Exception as e:
        _handle_analytics_error(e)


# ── Data Quality ──────────────────────────────────────────────────────────────

@router.get("/data-quality", tags=["Data Quality"])
async def get_data_quality(
    dataset_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(DataQualityReportModel)
        .where(DataQualityReportModel.dataset_id == dataset_id)
        .order_by(DataQualityReportModel.generated_at.desc())
        .limit(1)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="No data quality report found")
    return {
        "id": report.id,
        "dataset_id": report.dataset_id,
        "overall_status": report.overall_status,
        "total_rows": report.total_rows,
        "valid_rows": report.valid_rows,
        "duplicate_rows": report.duplicate_rows,
        "issues": report.issues,
        "warnings": report.warnings,
        "generated_at": str(report.generated_at),
    }


# ── Budgets ───────────────────────────────────────────────────────────────────

@router.get("/budgets", tags=["Budgets"])
async def list_budgets(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(select(Budget).order_by(Budget.created_at.desc()))
    budgets = result.scalars().all()
    return [{"id": b.id, "name": b.name, "budget_amount": b.budget_amount,
             "currency": b.currency, "period_type": b.period_type} for b in budgets]


@router.post("/budgets", tags=["Budgets"])
async def create_budget(
    body: BudgetCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    budget = Budget(
        id=str(uuid.uuid4()),
        name=body.name,
        entity_type=body.entity_type,
        entity_value=body.entity_value,
        period_type=body.period_type,
        period_start=datetime.combine(body.period_start, datetime.min.time()),
        period_end=datetime.combine(body.period_end, datetime.min.time()),
        budget_amount=body.budget_amount,
        currency=body.currency,
        created_by=current_user.id,
    )
    db.add(budget)
    await db.commit()
    return {"id": budget.id, "name": budget.name}
