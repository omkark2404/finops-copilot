"""
ARQ Background Worker.
Handles async jobs: ingestion, anomaly detection, forecasting, agent pipeline, scenarios.
"""
from __future__ import annotations
from arq import Worker
from arq.connections import RedisSettings

from .config import get_settings


async def ingest_dataset_task(ctx, dataset_id: str, file_path: str, dataset_name: str, source_url: str = None):
    from .ingestion import ingest_file
    return ingest_file(file_path, dataset_id, dataset_name, source_url)


async def run_anomaly_detection_task(ctx, dataset_id: str, entity_type: str = "service"):
    from .anomaly import run_anomaly_detection
    report = run_anomaly_detection(dataset_id, entity_type)
    return {"total_anomalies": report.total_anomalies, "critical": report.critical_count}


async def run_forecasting_task(ctx, dataset_id: str, horizon: int = 30):
    from .forecasting import forecast_total_spend
    result = forecast_total_spend(dataset_id, horizon)
    return {"method": result.method.value, "metrics": result.metrics}


async def run_agent_pipeline_task(ctx, dataset_id: str):
    from .agents import run_pipeline, get_llm_provider
    llm = get_llm_provider()
    result = await run_pipeline(dataset_id, llm)
    return {"pipeline_run_id": result.id, "status": result.status.value}


async def run_scenario_task(ctx, recommendation_id: str, scenario_type: str, config: dict):
    from .scenarios import run_scenario
    from .schemas import ScenarioType
    result = run_scenario(recommendation_id, ScenarioType(scenario_type), config)
    return result.model_dump()


class WorkerSettings:
    functions = [
        ingest_dataset_task,
        run_anomaly_detection_task,
        run_forecasting_task,
        run_agent_pipeline_task,
        run_scenario_task,
    ]
    on_startup = None
    on_shutdown = None

    @classmethod
    def get_redis_settings(cls) -> RedisSettings:
        settings = get_settings()
        return RedisSettings.from_dsn(settings.arq_redis_url)

    redis_settings = property(get_redis_settings)
