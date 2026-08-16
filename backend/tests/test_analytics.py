"""
Unit tests for deterministic cost analytics.

SYNTHETIC TEST FIXTURE — NOT REAL BILLING DATA.
Used only for isolated unit tests.
Never used for training, evaluation, or benchmark metrics.
"""
import pandas as pd
import pytest
from pathlib import Path
from datetime import datetime, timedelta
import tempfile
import os


# ── SYNTHETIC TEST FIXTURE (labelled) ─────────────────────────────────────────

def make_synthetic_focus_df(n_days=60, n_services=3) -> pd.DataFrame:
    """
    SYNTHETIC TEST FIXTURE — NOT REAL BILLING DATA.
    Generates minimal FOCUS-format data for unit testing only.
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


def test_synthetic_fixture_is_labelled():
    """Ensure the fixture is always labelled as synthetic."""
    df = make_synthetic_focus_df()
    assert len(df) > 0  # sanity
    # This test documents that the fixture is synthetic
    assert "SYNTHETIC" in make_synthetic_focus_df.__doc__


def test_spend_aggregation_basic():
    """Test basic spend aggregation logic."""
    df = make_synthetic_focus_df(n_days=10, n_services=2)
    total = df["billed_cost"].sum()
    assert total > 0
    assert isinstance(total, float)


def test_service_breakdown():
    """Test service-level cost breakdown."""
    df = make_synthetic_focus_df(n_days=10, n_services=3)
    breakdown = df.groupby("service")["billed_cost"].sum()
    assert len(breakdown) == 3
    assert all(v > 0 for v in breakdown.values)


def test_daily_trend():
    """Test daily spend trend computation."""
    df = make_synthetic_focus_df(n_days=14)
    df["day"] = df["charge_period_start"].dt.date
    daily = df.groupby("day")["billed_cost"].sum()
    assert len(daily) == 14
