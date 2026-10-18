"""Forecast candidates compared with recursive predictions on the same temporal windows."""

import logging
import warnings
from datetime import timedelta

import numpy as np
import pandas as pd

from .query import currency, dimension, execute
from .schemas import ForecastMethod, ForecastPoint, ForecastResult
from .time import utcnow

log = logging.getLogger(__name__)
RANDOM_SEED = 42


def _evaluate(actual, predicted):
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    if not len(actual) or len(actual) != len(predicted) or not np.isfinite(predicted).all():
        raise ValueError("Cannot evaluate empty, mismatched or nonfinite predictions")
    error = predicted - actual
    denominator = float(np.abs(actual).sum())
    return {
        "mae": round(float(np.abs(error).mean()), 4),
        "rmse": round(float(np.sqrt((error**2).mean())), 4),
        "wape": round(float(np.abs(error).sum()) / denominator, 4) if denominator else None,
        "bias": round(float(error.mean()), 4),
    }


def _series(series):
    series = series.sort_index().astype(float)
    if len(series) > 3660:
        raise ValueError(
            "Forecasts support at most 3660 daily observations; upload a smaller period"
        )
    if len(series) < 5 or not np.isfinite(series.values).all():
        raise ValueError("At least five finite daily observations are required")
    if not isinstance(series.index, pd.DatetimeIndex) or series.index.has_duplicates:
        raise ValueError("Unique calendar dates are required")
    if len(pd.date_range(series.index[0], series.index[-1], freq="D")) != len(series):
        raise ValueError(
            "Missing calendar days: resolve missing billing coverage before forecasting"
        )
    return series.asfreq("D")


def features(history, day):
    def lag(n):
        return history[-n] if len(history) >= n else np.nan

    def growth(n):
        old = lag(n + 1)
        return history[-1] / old - 1 if np.isfinite(old) and old != 0 else 0.0

    return {
        "lag_1": lag(1),
        "lag_7": lag(7),
        "lag_14": lag(14),
        "lag_28": lag(28),
        "mean_7": float(np.mean(history[-7:])),
        "mean_14": float(np.mean(history[-14:])),
        "std_7": float(np.std(history[-7:], ddof=1)),
        "weekday": day.dayofweek,
        "month": day.month,
        "growth_7": growth(7),
        "growth_28": growth(28),
    }


def _predict(method, series, horizon, window=7):
    values = series.values
    if method == "naive":
        return np.repeat(values[-1], horizon)
    if method == "moving_average":
        return np.repeat(np.mean(values[-window:]), horizon)
    if method == "exp_smoothing":
        from statsmodels.tools.sm_exceptions import ConvergenceWarning
        from statsmodels.tsa.holtwinters import ExponentialSmoothing

        seasonal = len(series) >= 21
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", ConvergenceWarning)
                fit = ExponentialSmoothing(
                    series,
                    trend="add",
                    seasonal="add" if seasonal else None,
                    seasonal_periods=7 if seasonal else None,
                ).fit(optimized=True, use_brute=False)
        except ConvergenceWarning as error:
            raise ValueError("Holt-Winters optimization did not converge") from error
        return np.asarray(fit.forecast(horizon))
    if method == "lightgbm":
        import lightgbm as lgb

        if len(series) < 60:
            raise ValueError("LightGBM needs at least 60 daily training points")
        x = pd.DataFrame(
            [
                features(list(values[max(0, i - 29) : i]), series.index[i])
                for i in range(28, len(values))
            ]
        )
        y = values[28:]
        model = lgb.LGBMRegressor(
            n_estimators=100,
            learning_rate=0.05,
            num_leaves=7,
            min_child_samples=5,
            random_state=RANDOM_SEED,
            n_jobs=1,
            verbosity=-1,
        )
        model.fit(x, y)
        history = list(values)
        pred = []
        for i in range(horizon):
            day = series.index[-1] + timedelta(days=i + 1)
            value = float(model.predict(pd.DataFrame([features(history, day)]))[0])
            history.append(value)
            pred.append(value)
        return np.asarray(pred)
    raise ValueError("Unsupported forecast method")


def _result(series, horizon, method, metrics, baseline=None, metadata=None):
    predictions = _predict(method, series, horizon)
    if len(predictions) != horizon or not np.isfinite(predictions).all():
        raise ValueError("Forecast returned invalid predictions")
    return ForecastResult(
        entity="total",
        method=ForecastMethod(method),
        forecast_horizon_days=horizon,
        points=[
            ForecastPoint(
                date=str(series.index[-1] + timedelta(days=i + 1))[:10],
                predicted_cost=round(float(v), 2),
            )
            for i, v in enumerate(predictions)
        ],
        metrics=metrics,
        baseline_metrics=baseline,
        training_period={
            "start": str(series.index[0])[:10],
            "end": str(series.index[-1])[:10],
            "missing_days": "rejected",
            **(metadata or {}),
        },
        model_version=f"{method}-v2",
        generated_at=utcnow(),
    )


def _single(series, horizon, method):
    series = _series(series)
    if not 1 <= horizon <= 90:
        raise ValueError("Horizon must be 1–90 days")
    split = max(2, int(len(series) * 0.8))
    metrics = _evaluate(
        series.iloc[split:], _predict(method, series.iloc[:split], len(series) - split)
    )
    return _result(series, horizon, method, metrics)


def naive_forecast(series, horizon):
    return _single(series, horizon, "naive")


def moving_average_forecast(series, horizon, window=7):
    return _single(series, horizon, "moving_average")


def exp_smoothing_forecast(series, horizon):
    return _single(series, horizon, "exp_smoothing")


def lightgbm_forecast(series, horizon, entity="total"):
    series = _series(series)
    if not 1 <= horizon <= 90:
        raise ValueError("Horizon must be 1–90 days")
    n = len(series)
    train_end = max(2, int(n * 0.6))
    val_end = max(train_end + 1, int(n * 0.8))
    candidates = ["naive", "moving_average"]
    if train_end >= 14:
        candidates.append("exp_smoothing")
    if train_end >= 60:
        candidates.append("lightgbm")
    scores = {}
    failures = {}
    # Identical fixed-origin multi-step validation; no observed future lags.
    for method in candidates:
        try:
            scores[method] = _evaluate(
                series.iloc[train_end:val_end],
                _predict(method, series.iloc[:train_end], val_end - train_end),
            )
        except (ValueError, RuntimeError, ImportError) as error:
            failures[method] = type(error).__name__
            log.warning("Forecast candidate failed: %s (%s)", method, type(error).__name__)
    winner = min(scores, key=lambda m: scores[m]["mae"])
    # Untouched test window after selection. Fit on train+validation, recurse across test.
    test = _evaluate(series.iloc[val_end:], _predict(winner, series.iloc[:val_end], n - val_end))
    baseline = _evaluate(
        series.iloc[val_end:], _predict("naive", series.iloc[:val_end], n - val_end)
    )
    result = _result(
        series,
        horizon,
        winner,
        test,
        baseline,
        {
            "protocol": "60/20/20 fixed-origin recursive",
            "validation_metrics": scores,
            "failed_candidates": failures,
            "test_start": str(series.index[val_end])[:10],
            "test_end": str(series.index[-1])[:10],
            "validation_horizon_days": val_end - train_end,
            "test_horizon_days": n - val_end,
            "requested_horizon_days": horizon,
            "selection_metric": "validation MAE",
            "refit": "all observed data",
        },
    )
    result.entity = entity
    return result


def forecast_entity(dataset_id, entity_type, entity_value, horizon_days=30):
    from .storage import download_dataset_parquet

    path = download_dataset_parquet(dataset_id)
    unit = currency(path)
    where, args = (
        ("", [])
        if entity_type == "total"
        else (f" WHERE CAST({dimension(entity_type)} AS VARCHAR)=?", [entity_value])
    )
    rows = execute(
        path,
        "SELECT DATE_TRUNC('day',charge_period_start)::DATE AS day,SUM(billed_cost) AS cost FROM {source}"
        + where
        + " GROUP BY 1 ORDER BY 1",
        args,
    ).fetchdf()
    if rows.empty:
        raise ValueError("No observations for this entity")
    series = rows.set_index(pd.DatetimeIndex(pd.to_datetime(rows["day"])))["cost"]
    result = lightgbm_forecast(series, horizon_days, entity=f"{entity_type}:{entity_value}")
    result.currency = unit
    return result


def forecast_total_spend(dataset_id, horizon_days=30):
    return forecast_entity(dataset_id, "total", "all", horizon_days)
