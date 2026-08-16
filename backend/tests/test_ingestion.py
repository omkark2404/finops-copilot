"""
Unit tests for FOCUS ingestion.

SYNTHETIC TEST FIXTURE — NOT REAL BILLING DATA.
"""
import hashlib
import tempfile
from pathlib import Path
import pandas as pd
import pytest


def make_focus_csv(tmp_path, rows=10) -> str:
    """
    SYNTHETIC TEST FIXTURE — NOT REAL BILLING DATA.
    Creates a minimal FOCUS 1.0 CSV for unit testing only.
    """
    data = {
        "BilledCost": [100.0 + i for i in range(rows)],
        "EffectiveCost": [95.0 + i for i in range(rows)],
        "BillingCurrency": ["USD"] * rows,
        "ProviderName": ["TestProvider"] * rows,
        "BillingAccountId": ["acc-001"] * rows,
        "ServiceName": ["Compute"] * rows,
        "RegionId": ["us-east-1"] * rows,
        "ChargePeriodStart": [f"2024-01-{i+1:02d}T00:00:00Z" for i in range(rows)],
        "ChargePeriodEnd": [f"2024-01-{i+1:02d}T23:59:59Z" for i in range(rows)],
    }
    df = pd.DataFrame(data)
    path = tmp_path / "synthetic_test_fixture.csv"
    df.to_csv(path, index=False)
    return str(path)


def test_detect_focus_version_v1_0(tmp_path):
    from app.ingestion import detect_focus_version
    from app.schemas import FocusVersion
    path = make_focus_csv(tmp_path)
    df = pd.read_csv(path)
    version = detect_focus_version(df)
    assert version == FocusVersion.v1_0


def test_normalize_columns(tmp_path):
    from app.ingestion import normalize_to_canonical, detect_focus_version
    path = make_focus_csv(tmp_path)
    df = pd.read_csv(path)
    version = detect_focus_version(df)
    canonical = normalize_to_canonical(df, version)
    assert "billed_cost" in canonical.columns
    assert "currency" in canonical.columns
    assert "charge_period_start" in canonical.columns


def test_null_rate_computation(tmp_path):
    from app.ingestion import validate_focus_data, normalize_to_canonical, detect_focus_version
    from app.schemas import FocusVersion
    path = make_focus_csv(tmp_path)
    df = pd.read_csv(path)
    version = detect_focus_version(df)
    canonical = normalize_to_canonical(df, version)
    report = validate_focus_data(canonical, version)
    assert "billed_cost" in report.null_rate_by_field
    assert report.null_rate_by_field["billed_cost"] == 0.0


def test_content_hash_deterministic(tmp_path):
    from app.ingestion import compute_file_hash
    path = make_focus_csv(tmp_path)
    h1 = compute_file_hash(str(path))
    h2 = compute_file_hash(str(path))
    assert h1 == h2
    assert len(h1) == 64  # SHA-256


def test_reject_missing_required_fields():
    from app.ingestion import validate_focus_data
    from app.schemas import FocusVersion, QualityStatus
    # SYNTHETIC TEST FIXTURE
    df = pd.DataFrame({"SomeRandomColumn": [1, 2, 3]})
    report = validate_focus_data(df, FocusVersion.v1_0)
    assert report.overall_status == QualityStatus.fail
    assert len(report.issues) > 0
