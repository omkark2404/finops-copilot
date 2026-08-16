"""
Unit tests for forecasting.

SYNTHETIC TEST FIXTURE — NOT REAL BILLING DATA.
"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import pytest


def make_trend_series(n=80, base=1000.0, growth=5.0) -> pd.Series:
    """
    SYNTHETIC TEST FIXTURE — NOT REAL BILLING DATA.
    Trending series with weekly seasonality for forecast testing.
    """
    dates = [datetime(2024, 1, 1) + timedelta(days=i) for i in range(n)]
    values = [base + growth * i + 50.0 * np.sin(i * 2 * np.pi / 7) for i in range(n)]
    return pd.Series(values, index=pd.DatetimeIndex(dates), dtype=float)


def test_naive_forecast_returns_last_value():
    from app.forecasting import naive_forecast
    series = make_trend_series(30)
    result = naive_forecast(series, horizon=7)
    assert len(result.points) == 7
    for p in result.points:
        assert p.predicted_cost == pytest.approx(float(series.iloc[-1]), rel=0.01)


def test_moving_average_forecast():
    from app.forecasting import moving_average_forecast
    series = make_trend_series(30)
    result = moving_average_forecast(series, horizon=7, window=7)
    assert len(result.points) == 7
    assert all(p.predicted_cost > 0 for p in result.points)


def test_evaluate_metrics():
    from app.forecasting import _evaluate
    actual = np.array([100.0, 110.0, 120.0, 130.0])
    pred = np.array([105.0, 115.0, 125.0, 135.0])
    metrics = _evaluate(actual, pred)
    assert "mae" in metrics
    assert "rmse" in metrics
    assert "wape" in metrics
    assert "bias" in metrics
    assert metrics["mae"] == pytest.approx(5.0, rel=0.01)
    assert metrics["bias"] == pytest.approx(5.0, rel=0.01)


def test_no_future_leakage():
    """Verify features are only computed from past data."""
    from app.forecasting import exp_smoothing_forecast
    series = make_trend_series(80)
    result = exp_smoothing_forecast(series, horizon=10)
    assert result.training_period is not None
    assert "start" in result.training_period
    assert "end" in result.training_period
