"""
Unit tests for statistical anomaly detection.

SYNTHETIC TEST FIXTURE — NOT REAL BILLING DATA.
"""
import numpy as np
import pandas as pd
import pytest
from datetime import datetime, timedelta


def make_flat_series(n=30, value=100.0, spike_day=None, spike_val=500.0) -> pd.Series:
    """
    SYNTHETIC TEST FIXTURE — NOT REAL BILLING DATA.
    Creates a flat time series with an optional spike for testing.
    """
    dates = [datetime(2024, 1, 1) + timedelta(days=i) for i in range(n)]
    values = [value] * n
    if spike_day is not None:
        values[spike_day] = spike_val
    return pd.Series(values, index=pd.DatetimeIndex(dates), dtype=float)


def test_robust_zscore_detects_spike():
    """Robust Z-score should detect a clear spike."""
    from app.anomaly import detect_robust_zscore
    series = make_flat_series(n=30, value=100.0, spike_day=15, spike_val=800.0)
    anomalies = detect_robust_zscore(series, "service", "test", "ds_test")
    assert len(anomalies) >= 1
    dates = [a.detected_at for a in anomalies]
    assert any("2024-01-16" in d for d in dates)


def test_rolling_zscore_detects_spike():
    from app.anomaly import detect_rolling_zscore
    series = make_flat_series(n=30, value=100.0, spike_day=20, spike_val=600.0)
    anomalies = detect_rolling_zscore(series, "service", "test", "ds_test")
    assert len(anomalies) >= 1


def test_no_false_positives_on_flat():
    """Flat series with no spike should produce no or minimal anomalies."""
    from app.anomaly import detect_robust_zscore
    series = make_flat_series(n=30, value=100.0)
    anomalies = detect_robust_zscore(series, "service", "test", "ds_test")
    assert len(anomalies) == 0


def test_classify_severity():
    from app.anomaly import classify_severity
    from app.schemas import AnomalySeverity
    assert classify_severity(10) == AnomalySeverity.low
    assert classify_severity(30) == AnomalySeverity.medium
    assert classify_severity(75) == AnomalySeverity.high
    assert classify_severity(150) == AnomalySeverity.critical
    assert classify_severity(-150) == AnomalySeverity.critical


def test_ewma_detects_spike():
    from app.anomaly import detect_ewma
    series = make_flat_series(n=40, value=200.0, spike_day=30, spike_val=1000.0)
    anomalies = detect_ewma(series, "service", "test", "ds_test", threshold=1.5)
    assert len(anomalies) >= 1
