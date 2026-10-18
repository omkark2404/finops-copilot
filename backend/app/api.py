"""Authenticated HTTP contracts for the single-process billing prototype."""

import asyncio
import hashlib
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
)
from pydantic import BaseModel, Field
from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .agents import get_llm_provider, run_pipeline
from .analytics import (
    get_cost_drivers,
    get_resource_breakdown,
    get_spend_summary,
    get_spend_trend,
)
from .anomaly import run_anomaly_detection
from .auth import (
    create_access_token,
    get_current_user,
    hash_password,
    log_audit,
    require_role,
    verify_password,
)
from .config import get_settings
from .db import get_db
from .execution import compute
from .forecasting import forecast_total_spend
from .ingestion import ingest_file
from .models import (
    AgentRunModel,
    AnomalyModel,
    Budget,
    DataQualityReportModel,
    Dataset,
    ForecastModel,
    IngestionRun,
    Investigation,
    OpportunityModel,
    PipelineRun,
    RecommendationModel,
    SavingsEstimateModel,
    ScenarioRun,
    User,
)
from .optimization import run_optimization_analysis
from .scenarios import run_scenario
from .schemas import BudgetCreate, LoginRequest, ScenarioType, UserCreate, UserRole
from .storage import delete_dataset_storage, get_uploads_dir, validate_dataset_id
from .time import utcnow

router = APIRouter()
log = logging.getLogger(__name__)
WRITERS = (UserRole.admin, UserRole.finops_analyst, UserRole.engineering_manager)
writer = require_role(*WRITERS)


def visible(query, model, user):
    return query if user.role == "ADMIN" else query.where(model.created_by == user.id)


async def dataset_access(dataset_id: str, db: AsyncSession, user):
    try:
        ident = validate_dataset_id(dataset_id)
    except ValueError:
        raise HTTPException(400, "Invalid dataset ID")
    dataset = (
        await db.execute(visible(select(Dataset).where(Dataset.id == ident), Dataset, user))
    ).scalar_one_or_none()
    if dataset is None:
        raise HTTPException(404, "Dataset not found")
    return dataset


async def checked_dataset(dataset_id: str, db=Depends(get_db), user=Depends(get_current_user)):
    return await dataset_access(dataset_id, db, user)


def dataset_json(d):
    return {
        "id": d.id,
        "name": d.name,
        "row_count": d.row_count,
        "validation_status": d.validation_status,
        "ingested_at": d.ingested_at,
        "focus_version": d.focus_version,
        "currency": d.currency,
        "date_range_start": d.date_range_start,
        "date_range_end": d.date_range_end,
    }


async def analysis(fn, *args, **kwargs):
    try:
        return await compute(fn, *args, **kwargs)
    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(404, "DATASET_STORAGE_MISSING: re-upload the billing file")
    except ValueError as error:
        raise HTTPException(400, str(error))
    except Exception:
        log.exception("Analysis failed")
        raise HTTPException(500, "Analysis failed; use the request ID when reporting the error")


@router.get("/health")
async def health(db=Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
        ok = True
    except Exception:
        ok = False
    return Response(
        content=__import__("json").dumps(
            {
                "status": "ok" if ok else "degraded",
                "database": "ok" if ok else "error",
                "database_backend": db.get_bind().dialect.name,
                "cache": "not_used",
                "version": get_settings().version,
                "llm_available": bool(get_settings().gemini_api_key),
                "llm_provider": "Gemini (configured, unverified)"
                if get_settings().gemini_api_key
                else "Offline",
            }
        ),
        status_code=200 if ok else 503,
        media_type="application/json",
    )


@router.get("/live")
def live():
    return {"status": "alive"}


@router.post("/auth/login")
async def login(body: LoginRequest, response: Response, db=Depends(get_db)):
    user = (await db.execute(select(User).where(User.email == body.email))).scalar_one_or_none()
    if not user or not user.is_active or not verify_password(body.password, user.hashed_password):
        raise HTTPException(401, "Invalid credentials")
    settings = get_settings()
    token = create_access_token({"sub": user.email, "role": user.role})
    response.set_cookie(
        "finops_session",
        token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.jwt_access_token_expire_minutes * 60,
        path="/",
    )
    await log_audit(db, user.id, "login", "user", user.id, None, None)
    return {"access_token": token, "token_type": "bearer"}


@router.get("/auth/me")
async def me(user=Depends(get_current_user)):
    return {"id": user.id, "email": user.email, "role": user.role}


@router.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie(
        "finops_session",
        path="/",
        secure=get_settings().cookie_secure,
        samesite=get_settings().cookie_samesite,
    )
    return {"status": "signed_out"}


@router.post("/auth/register", dependencies=[Depends(require_role(UserRole.admin))])
async def register(body: UserCreate, db=Depends(get_db)):
    if (await db.execute(select(User).where(User.email == body.email))).scalar_one_or_none():
        raise HTTPException(409, "Email already registered")
    try:
        hashed = hash_password(body.password)
    except ValueError as error:
        raise HTTPException(422, str(error))
    user = User(id=str(uuid4()), email=body.email, hashed_password=hashed, role=body.role.value)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
    }


@router.post("/datasets/ingest")
async def ingest_dataset(
    file: UploadFile = File(...),
    dataset_name: str = Form(..., min_length=1, max_length=120),
    source_url: str | None = Form(None, max_length=2000),
    db=Depends(get_db),
    user=Depends(writer),
):
    owner_id = user.id  # Rollback expires ORM objects; keep this immutable identity locally.
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".csv", ".parquet", ".pq"}:
        raise HTTPException(415, "Upload a CSV or Parquet file")
    ident = str(uuid4())
    path = get_uploads_dir() / f"{ident}{suffix}"
    size = 0
    digest = hashlib.sha256()
    committed = False
    try:
        with path.open("wb") as target:
            while chunk := await file.read(65536):
                size += len(chunk)
                if size > get_settings().max_upload_bytes:
                    raise HTTPException(413, "Upload exceeds configured byte limit")
                digest.update(chunk)
                target.write(chunk)
        if not size:
            raise HTTPException(422, "Upload is empty")
        prior = (
            await db.execute(
                select(Dataset).where(
                    Dataset.created_by == owner_id,
                    Dataset.content_hash == digest.hexdigest(),
                )
            )
        ).scalar_one_or_none()
        if prior:
            raise HTTPException(
                409,
                "This file is already ingested; delete the prior dataset to re-ingest",
            )
        provenance, dq = await analysis(ingest_file, str(path), ident, dataset_name, source_url)

        def dt(key):
            return (
                datetime.fromisoformat(provenance[key]).replace(tzinfo=None)
                if provenance.get(key)
                else None
            )

        dataset = Dataset(
            id=ident,
            name=dataset_name,
            source_url=source_url,
            file_path=None,
            created_by=owner_id,
            row_count=provenance["row_count"],
            content_hash=provenance["content_hash"],
            focus_version=provenance["focus_version"],
            parquet_path=provenance["parquet_path"],
            currency=provenance["currency"],
            ingested_at=utcnow(),
            validation_status=dq.overall_status.value,
            date_range_start=dt("date_range_start"),
            date_range_end=dt("date_range_end"),
        )
        db.add(dataset)
        await db.flush()
        db.add(
            DataQualityReportModel(
                id=str(uuid4()),
                dataset_id=ident,
                overall_status=dq.overall_status.value,
                total_rows=dq.total_rows,
                valid_rows=dq.valid_rows,
                duplicate_rows=dq.duplicate_rows,
                quality_data=dq.model_dump(mode="json"),
                issues=dq.issues,
                warnings=dq.warnings,
            )
        )
        await db.commit()
        committed = True
        await log_audit(
            db,
            owner_id,
            "ingest",
            "dataset",
            ident,
            {"sha256": digest.hexdigest(), "rows": provenance["row_count"]},
            None,
        )
        return {
            "dataset_id": ident,
            "dataset_name": dataset_name,
            "status": "succeeded",
            "row_count": provenance["row_count"],
            "validation_status": dq.overall_status.value,
            "issues": dq.issues,
            "warnings": dq.warnings,
        }
    except IntegrityError:
        # The unique index is authoritative when simultaneous requests pass the pre-check.
        await db.rollback()
        if not committed:
            delete_dataset_storage(ident)
        existing = (
            await db.execute(
                select(Dataset.id).where(
                    Dataset.created_by == owner_id, Dataset.content_hash == digest.hexdigest()
                )
            )
        ).scalar_one_or_none()
        if existing is not None and existing != ident:
            raise HTTPException(
                409, "This file is already ingested; delete the prior dataset to re-ingest"
            ) from None
        log.exception("Dataset integrity check failed")
        raise HTTPException(
            500, "Dataset could not be saved; use the request ID when reporting the error"
        ) from None
    except Exception:
        await db.rollback()
        if not committed:
            delete_dataset_storage(ident)
        raise
    finally:
        path.unlink(missing_ok=True)
        await file.close()


@router.get("/datasets")
async def list_datasets(db=Depends(get_db), user=Depends(get_current_user)):
    rows = (
        await db.execute(
            visible(select(Dataset), Dataset, user).order_by(Dataset.created_at.desc())
        )
    ).scalars()
    return [dataset_json(d) for d in rows]


@router.get("/datasets/{dataset_id}")
async def get_dataset(dataset=Depends(checked_dataset)):
    return dataset_json(dataset)


@router.delete("/datasets/{dataset_id}")
async def delete_dataset(dataset_id: str, db=Depends(get_db), user=Depends(writer)):
    dataset = await dataset_access(dataset_id, db, user)
    ident = dataset.id
    recs = select(RecommendationModel.id).where(RecommendationModel.dataset_id == ident)
    pipes = select(PipelineRun.id).where(PipelineRun.dataset_id == ident)
    anomalies = select(AnomalyModel.id).where(AnomalyModel.dataset_id == ident)
    await db.execute(delete(ScenarioRun).where(ScenarioRun.recommendation_id.in_(recs)))
    await db.execute(
        delete(SavingsEstimateModel).where(SavingsEstimateModel.recommendation_id.in_(recs))
    )
    await db.execute(
        delete(Investigation).where(
            (Investigation.pipeline_run_id.in_(pipes)) | (Investigation.anomaly_id.in_(anomalies))
        )
    )
    await db.execute(delete(AgentRunModel).where(AgentRunModel.pipeline_run_id.in_(pipes)))
    for model in [
        RecommendationModel,
        OpportunityModel,
        PipelineRun,
        AnomalyModel,
        ForecastModel,
        DataQualityReportModel,
        IngestionRun,
    ]:
        await db.execute(delete(model).where(model.dataset_id == ident))
    await db.delete(dataset)
    await analysis(delete_dataset_storage, ident)
    await db.commit()
    await log_audit(db, user.id, "delete", "dataset", ident, None, None)
    return {"status": "success"}


@router.get("/spend/summary")
async def spend_summary(
    period_start: date | None = None,
    period_end: date | None = None,
    dataset=Depends(checked_dataset),
):
    return await analysis(get_spend_summary, dataset.id, period_start, period_end)


@router.get("/spend/trend")
async def spend_trend(
    granularity: Literal["daily", "weekly", "monthly"] = "daily",
    period_start: date | None = None,
    period_end: date | None = None,
    dataset=Depends(checked_dataset),
):
    return await analysis(get_spend_trend, dataset.id, granularity, period_start, period_end)


@router.get("/spend/breakdown")
async def spend_breakdown(
    dimension: str = "service",
    period_start: date | None = None,
    period_end: date | None = None,
    limit: int = Query(25, ge=1, le=1000),
    dataset=Depends(checked_dataset),
):
    return await analysis(
        get_resource_breakdown, dataset.id, dimension, period_start, period_end, limit
    )


@router.get("/anomalies")
async def anomalies(
    entity_type: Literal["service", "provider", "account", "region"] = "service",
    dataset=Depends(checked_dataset),
):
    return await analysis(run_anomaly_detection, dataset.id, entity_type)


@router.get("/forecasts")
async def forecasts(horizon_days: int = Query(30, ge=1, le=90), dataset=Depends(checked_dataset)):
    return await analysis(forecast_total_spend, dataset.id, horizon_days)


@router.get("/opportunities")
async def opportunities(dataset=Depends(checked_dataset)):
    def run():
        attribution = get_cost_drivers(dataset.id)
        anomalies = run_anomaly_detection(dataset.id)
        return run_optimization_analysis(dataset.id, attribution, anomalies.anomalies)

    return await analysis(run)


@router.get("/data-quality")
async def quality(dataset=Depends(checked_dataset), db=Depends(get_db)):
    report = (
        (
            await db.execute(
                select(DataQualityReportModel)
                .where(DataQualityReportModel.dataset_id == dataset.id)
                .order_by(DataQualityReportModel.generated_at.desc())
            )
        )
        .scalars()
        .first()
    )
    if not report:
        raise HTTPException(404, "No quality report")
    return report.quality_data


@router.post("/agent-runs")
async def trigger_pipeline(dataset_id: str, db=Depends(get_db), user=Depends(writer)):
    dataset = await dataset_access(dataset_id, db, user)

    # Pipeline runs in a worker thread, bounded by compute(), without blocking the HTTP event loop.
    async def run_with_provider():
        provider = get_llm_provider()
        try:
            return await run_pipeline(dataset.id, provider)
        finally:
            if hasattr(provider, "close"):
                await provider.close()

    result = await analysis(lambda: asyncio.run(run_with_provider()))
    payload = result.model_dump(mode="json")
    run = PipelineRun(
        id=result.id,
        dataset_id=dataset.id,
        status=result.status.value,
        started_at=result.started_at,
        completed_at=result.completed_at,
        final_decision=payload.get("final_decision"),
        payload=payload,
        created_by=user.id,
    )
    db.add(run)
    await db.flush()
    for item in result.agent_runs:
        db.add(
            AgentRunModel(
                id=item.id,
                pipeline_run_id=result.id,
                agent_type=item.agent_type.value,
                status=item.status.value,
                started_at=item.started_at,
                completed_at=item.completed_at,
                duration_seconds=item.duration_seconds,
                input_data=item.input_summary,
                output_data=item.output_summary,
                confidence=item.confidence,
                error_message=item.error_message,
                retry_count=item.retry_count,
            )
        )
    for item in result.recommendations:
        db.add(
            RecommendationModel(
                id=item.id,
                dataset_id=dataset.id,
                pipeline_run_id=result.id,
                title=item.title,
                description=item.description,
                actions=[a.model_dump(mode="json") for a in item.actions],
                priority_rank=item.priority_rank,
                risk_level=item.risk_level,
                evidence=item.evidence,
                status=item.status.value,
                explanation=item.explanation,
            )
        )
    await db.commit()
    await log_audit(db, user.id, "run_analysis", "dataset", dataset.id, {"run_id": result.id}, None)
    return payload


@router.get("/agent-runs")
async def agent_runs(dataset=Depends(checked_dataset), db=Depends(get_db)):
    rows = (
        await db.execute(
            select(PipelineRun)
            .where(PipelineRun.dataset_id == dataset.id)
            .order_by(PipelineRun.started_at.desc())
            .limit(20)
        )
    ).scalars()
    return [r.payload for r in rows]


@router.get("/recommendations")
async def recommendations(dataset=Depends(checked_dataset), db=Depends(get_db)):
    rows = (
        await db.execute(
            select(RecommendationModel)
            .where(RecommendationModel.dataset_id == dataset.id)
            .order_by(RecommendationModel.created_at.desc())
            .limit(100)
        )
    ).scalars()
    return [
        {
            "id": r.id,
            "title": r.title,
            "description": r.description,
            "evidence": r.evidence,
            "status": r.status,
            "risk_level": r.risk_level,
            "explanation": r.explanation,
        }
        for r in rows
    ]


class Decision(BaseModel):
    decision: Literal["approved", "rejected"]


async def recommendation_access(ident, db, user):
    rec = await db.get(RecommendationModel, ident)
    if not rec:
        raise HTTPException(404, "Recommendation not found")
    dataset = await dataset_access(rec.dataset_id, db, user)
    return rec, dataset


@router.post("/recommendations/{ident}/decision")
async def decide(ident: str, body: Decision, db=Depends(get_db), user=Depends(writer)):
    rec, dataset = await recommendation_access(ident, db, user)
    run = await db.get(PipelineRun, rec.pipeline_run_id)
    if body.decision == "approved" and not (
        run and (run.payload or {}).get("validation", {}).get("recommendation_safe")
    ):
        raise HTTPException(409, "Checklist has unresolved issues; review before approval")
    rec.status = body.decision
    rec.approved_by = user.id
    rec.approved_at = utcnow()
    await db.commit()
    await log_audit(
        db,
        user.id,
        body.decision,
        "recommendation",
        ident,
        {"dataset_id": dataset.id},
        None,
    )
    return {
        "status": rec.status,
        "note": "Human review recorded; no cloud resources are modified",
    }


class ScenarioInput(BaseModel):
    reduction_pct: float = Field(gt=0, lt=100, allow_inf_nan=False)


@router.post("/recommendations/{ident}/simulate")
async def simulate(ident: str, body: ScenarioInput, db=Depends(get_db), user=Depends(writer)):
    rec, dataset = await recommendation_access(ident, db, user)
    summary = await analysis(get_spend_summary, dataset.id)
    if summary.total_billed_cost <= 0:
        raise HTTPException(400, "A positive observed baseline is required")
    days = (
        date.fromisoformat(summary.period_end) - date.fromisoformat(summary.period_start)
    ).days + 1
    estimate = run_scenario(
        ident,
        ScenarioType.usage_reduction,
        {
            "current_cost": summary.total_billed_cost,
            "reduction_pct": body.reduction_pct,
            "time_horizon_days": days,
            "entity": "entire observed dataset",
        },
    )
    payload = estimate.model_dump(mode="json")
    payload.update(
        currency=summary.currency,
        period_start=summary.period_start,
        period_end=summary.period_end,
        scope="Entire observed dataset, not a recommendation-specific achievable saving",
    )
    db.add(
        ScenarioRun(
            id=str(uuid4()),
            recommendation_id=ident,
            scenario_type="usage_reduction",
            scenario_config=body.model_dump(),
            result=payload,
            created_by=user.id,
        )
    )
    await db.commit()
    await log_audit(db, user.id, "simulate", "recommendation", ident, body.model_dump(), None)
    return payload


@router.get("/budgets")
async def list_budgets(db=Depends(get_db), user=Depends(get_current_user)):
    budgets = (
        await db.execute(visible(select(Budget), Budget, user).order_by(Budget.created_at.desc()))
    ).scalars()
    datasets = (await db.execute(visible(select(Dataset), Dataset, user))).scalars().all()
    results = []
    for budget in budgets:
        matching = [d for d in datasets if d.currency == budget.currency]
        # One budget uses one dataset to prevent overlapping export double-counting.
        actual = None
        if len(matching) == 1:
            summary = await analysis(
                get_spend_summary,
                matching[0].id,
                budget.period_start.date(),
                budget.period_end.date(),
            )
            actual = summary.total_billed_cost
        results.append(
            {
                "id": budget.id,
                "name": budget.name,
                "budget_amount": budget.budget_amount,
                "currency": budget.currency,
                "period_type": budget.period_type,
                "period_start": budget.period_start,
                "period_end": budget.period_end,
                "actual_spend": actual,
                "variance": round(actual - budget.budget_amount, 2) if actual is not None else None,
                "note": "Observed uploaded rows only; full budget-period coverage is not guaranteed"
                if actual is not None
                else "Exactly one visible matching-currency dataset is required to calculate observed variance",
            }
        )
    return results


@router.post("/budgets")
async def create_budget(body: BudgetCreate, db=Depends(get_db), user=Depends(writer)):
    if body.entity_type != "total":
        raise HTTPException(422, "Only whole-dataset budgets are supported")
    budget = Budget(
        id=str(uuid4()),
        **body.model_dump(exclude={"period_start", "period_end"}),
        period_start=datetime.combine(body.period_start, datetime.min.time()),
        period_end=datetime.combine(body.period_end, datetime.min.time()),
        created_by=user.id,
    )
    db.add(budget)
    await db.commit()
    await log_audit(db, user.id, "create", "budget", budget.id, None, None)
    return {"id": budget.id, "name": budget.name}
