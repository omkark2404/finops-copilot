"""
Unit tests for deterministic cost analytics.

SYNTHETIC TEST FIXTURE — NOT REAL BILLING DATA.
"""
import pandas as pd
import pytest
from pathlib import Path
from datetime import datetime, timedelta
import tempfile
import os

from app.analytics import get_spend_summary, get_spend_trend, get_cost_drivers, get_resource_breakdown


# ── SYNTHETIC TEST FIXTURE (labelled) ─────────────────────────────────────────

def make_synthetic_focus_df(n_days=60, n_services=3) -> pd.DataFrame:
    """
    SYNTHETIC TEST FIXTURE — NOT REAL BILLING DATA.
        """
    rows = []
    base = datetime(2024, 1, 1)
    services = [f"service_{i}" for i in range(n_services)]
    for day in range(n_days):
        dt = base + timedelta(days=day)
        for svc in services:
            rows.append({
                "billed_cost": 100.0 + day * 0.5 + (50.0 if svc == "service_0" else 0),
                "effective_cost": 95.0 + day * 0.5,
                "charge_period_start": dt,
                "charge_period_end": dt + timedelta(days=1),
                "currency": "USD",
                "provider": "TestProvider",
                "account": "test_account",
                "service": svc,
                "region": "us-east-1",
                "category": "Compute",
                "resource": f"resource_{svc}",
            })
    return pd.DataFrame(rows)


@pytest.fixture
def synthetic_parquet(monkeypatch):
    df = make_synthetic_focus_df(n_days=10, n_services=2)
    fd, path = tempfile.mkstemp(suffix=".parquet")
    os.close(fd)
    df.to_parquet(path)
    
    # Mock _get_parquet_path to return our temp file
    monkeypatch.setattr("app.analytics._get_parquet_path", lambda dataset_id: path)
    
    # We must ensure DuckDB can read it. DuckDB runs in the same process.
    yield path
    
    os.remove(path)


def test_synthetic_fixture_is_labelled():
    """Ensure the fixture is always labelled as synthetic."""
    df = make_synthetic_focus_df()
    assert len(df) > 0  # sanity
    # This test documents that the fixture is synthetic
    assert "SYNTHETIC" in make_synthetic_focus_df.__doc__


def test_get_spend_summary(synthetic_parquet):
    """Test actual application logic for spend summary."""
    summary = get_spend_summary("test_dataset_id")
    assert summary.total_billed_cost > 0
    assert summary.currency == "USD"
    assert "service_0" in summary.service_breakdown
    assert "service_1" in summary.service_breakdown
    assert summary.service_breakdown["service_0"] > summary.service_breakdown["service_1"]


def test_get_spend_trend(synthetic_parquet):
    """Test actual application logic for spend trend computation."""
    trend = get_spend_trend("test_dataset_id", granularity="daily")
    assert len(trend.data_points) == 10
    assert trend.data_points[0].billed_cost > 0
    assert trend.granularity == "daily"


def test_get_cost_drivers(synthetic_parquet):
    """Test actual application logic for finding top cost drivers."""
    drivers = get_cost_drivers("test_dataset_id")
    assert len(drivers.top_drivers) > 0
    assert drivers.top_drivers[0].dimension in ["provider", "account", "service", "region"]
    assert drivers.total_cost > 0


def test_get_resource_breakdown(synthetic_parquet):
    """Test actual application logic for dimension breakdown."""
    breakdown = get_resource_breakdown("test_dataset_id", dimension="service")
    assert len(breakdown) == 2
    assert breakdown[0]["billed_cost"] > 0
    assert breakdown[0]["row_count"] == 10
