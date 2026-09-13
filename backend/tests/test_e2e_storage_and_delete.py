import pytest
import asyncio
import os
import shutil
import uuid
from pathlib import Path
import pandas as pd

from app.storage import (
    get_data_dir, get_dataset_dir, get_dataset_parquet_path,
    verify_dataset_parquet_exists
)
from app.ingestion import ingest_file
from app.analytics import get_spend_summary, get_spend_trend
from app.anomaly import run_anomaly_detection
from app.forecasting import forecast_total_spend
from app.optimization import run_optimization_analysis
from app.config import get_settings


@pytest.mark.asyncio
async def test_e2e_ingest_analytics_missing_and_delete(tmp_path, monkeypatch):
    test_dir = str(tmp_path / "e2e_storage_test")
    monkeypatch.setenv("DATA_DIR", test_dir)
    get_settings.cache_clear()

    # 1. Create sample CSV
    csv_file = tmp_path / "sample_focus.csv"
    csv_file.write_text(
        "BilledCost,EffectiveCost,ChargePeriodStart,ChargePeriodEnd,BillingCurrency,ProviderName,ServiceName\n"
        "10.5,10.5,2024-01-01T00:00:00Z,2024-01-01T01:00:00Z,USD,AWS,Amazon EC2\n"
        "20.0,20.0,2024-01-02T00:00:00Z,2024-01-02T01:00:00Z,USD,AWS,Amazon S3\n"
    )

    dataset_id = str(uuid.uuid4())

    # 2. Ingest file
    provenance, dq_report = ingest_file(str(csv_file), dataset_id, "Test E2E Dataset")
    assert provenance["row_count"] == 2
    assert dq_report.overall_status.value == "PASS"

    # 3. Verify parquet created under DATA_DIR/parquet/<dataset_id>/data.parquet
    parquet_path = get_dataset_parquet_path(dataset_id)
    assert parquet_path.exists()
    assert str(parquet_path).startswith(str(Path(test_dir).resolve()))

    # 4. Run analytics successfully
    summary = get_spend_summary(dataset_id)
    assert summary.total_billed_cost == 30.5

    trend = get_spend_trend(dataset_id)
    assert len(trend.data_points) == 2

    # 5. Simulate missing Parquet (e.g. Render restart before disk attach)
    os.remove(parquet_path)

    # 6. Verify analytics returns FileNotFoundError with DATASET_STORAGE_MISSING detail
    with pytest.raises(FileNotFoundError) as exc_info:
        get_spend_summary(dataset_id)
    assert "DATASET_STORAGE_MISSING" in str(exc_info.value)

    # 7. Clean up storage directory
    dataset_dir = get_dataset_dir(dataset_id)
    shutil.rmtree(dataset_dir, ignore_errors=True)
    assert not dataset_dir.exists()

    get_settings.cache_clear()
