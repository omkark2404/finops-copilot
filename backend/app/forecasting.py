"""
Time-Series Forecasting.

Progression:
  Naive baseline → Moving Average → Exponential Smoothing → LightGBM

Strict temporal splits — no future leakage:
  TRAIN = earlier billing periods
  VAL = later billing periods  
  TEST = latest unseen billing periods

NEVER randomly shuffle time-series records.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from .config import get_settings
from .db import get_duck
from .schemas import ForecastMethod, ForecastPoint, ForecastResult

RANDOM_SEED = 42
MIN_TRAIN_POINTS = 14


def _evaluate(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    """Compute MAE, RMSE, WAPE, and bias. All deterministic."""
    if len(actual) == 0:
        return {"mae": float("inf"), "rmse": float("inf"), "wape": float("inf"), "bias": 0.0}
    mae = float(np.mean(np.abs(actual - predicted)))
    rmse = float(np.sqrt(np.mean((actual - predicted) ** 2)))
    wape = float(np.sum(np.abs(actual - predicted)) / np.sum(np.abs(actual))) if np.sum(np.abs(actual)) > 0 else float("inf")
    bias = float(np.mean(predicted - actual))
    return {"mae": round(mae, 4), "rmse": round(rmse, 4), "wape": round(wape, 4), "bias": round(bias, 4)}


def naive_forecast(series: pd.Series, horizon: int) -> ForecastResult:
    """Naive: use last observed value for all future periods."""
    last_val = float(series.iloc[-1])
    last_date = series.index[-1]
    points = [
        ForecastPoint(date=str(last_date + timedelta(days=i + 1))[:10], predicted_cost=round(last_val, 2))
        for i in range(horizon)
    ]
    # Evaluate on last 20% of series
    n = len(series)
    if n >= 5:
        split = max(1, int(n * 0.8))
        actual_eval = series.values[split:]
        pred_eval = np.full(len(actual_eval), float(series.values[split - 1]))
        metrics = _evaluate(actual_eval, pred_eval)
    else:
        metrics = {"mae": 0, "rmse": 0, "wape": 0, "bias": 0}

    return ForecastResult(
        entity="total",
        method=ForecastMethod.naive,
        forecast_horizon_days=horizon,
        points=points,
        metrics=metrics,
        training_period={"start": str(series.index[0])[:10], "end": str(series.index[-1])[:10]},
        model_version="naive-v1",
        generated_at=datetime.utcnow(),
    )


def moving_average_forecast(series: pd.Series, horizon: int, window: int = 7) -> ForecastResult:
    """Moving average forecast."""
    if len(series) < window:
        return naive_forecast(series, horizon)
    ma_val = float(series.rolling(window=window).mean().iloc[-1])
    last_date = series.index[-1]
    points = [
        ForecastPoint(date=str(last_date + timedelta(days=i + 1))[:10], predicted_cost=round(ma_val, 2))
        for i in range(horizon)
    ]
    n = len(series)
    if n >= window + 2:
        split = max(window, int(n * 0.8))
        actual_eval = series.values[split:]
        pred_eval = np.array([float(series.values[max(0, i - window):i].mean()) for i in range(split, n)])
        metrics = _evaluate(actual_eval, pred_eval)
    else:
        metrics = {"mae": 0, "rmse": 0, "wape": 0, "bias": 0}

    return ForecastResult(
        entity="total",
        method=ForecastMethod.moving_average,
        forecast_horizon_days=horizon,
        points=points,
        metrics=metrics,
        training_period={"start": str(series.index[0])[:10], "end": str(series.index[-1])[:10], "window": str(window)},
        model_version=f"ma-{window}d-v1",
        generated_at=datetime.utcnow(),
    )


def exp_smoothing_forecast(series: pd.Series, horizon: int) -> ForecastResult:
    """Exponential smoothing forecast via statsmodels."""
    try:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing
        n = len(series)
        if n < 10:
            return moving_average_forecast(series, horizon)

        split = max(7, int(n * 0.8))
        train = series.iloc[:split]
        val = series.iloc[split:]

        # Try Holt-Winters with seasonal component if enough data
        use_seasonal = len(train) >= 21
        try:
            if use_seasonal:
                model = ExponentialSmoothing(train, trend='add', seasonal='add', seasonal_periods=7)
            else:
                model = ExponentialSmoothing(train, trend='add')
            fit = model.fit(optimized=True, use_brute=False)
        except Exception:
            model = ExponentialSmoothing(train)
            fit = model.fit()

        val_pred = fit.forecast(len(val))
        metrics = _evaluate(val.values, val_pred.values)

        # Refit on full series for final forecast
        full_model = ExponentialSmoothing(series, trend='add' if not use_seasonal else 'add',
                                          seasonal='add' if use_seasonal else None,
                                          seasonal_periods=7 if use_seasonal else None)
        full_fit = full_model.fit(optimized=True, use_brute=False)
        forecast = full_fit.forecast(horizon)

        last_date = series.index[-1]
        points = [
            ForecastPoint(
                date=str(last_date + timedelta(days=i + 1))[:10],
                predicted_cost=round(max(0, float(forecast.iloc[i])), 2)
            )
            for i in range(horizon)
        ]

        return ForecastResult(
            entity="total",
            method=ForecastMethod.exp_smoothing,
            forecast_horizon_days=horizon,
            points=points,
            metrics=metrics,
            training_period={"start": str(series.index[0])[:10], "end": str(series.index[-1])[:10]},
            model_version="holtwinters-v1",
            generated_at=datetime.utcnow(),
        )
    except Exception as e:
        return moving_average_forecast(series, horizon)


def lightgbm_forecast(series: pd.Series, horizon: int, entity: str = "total") -> ForecastResult:
    """
    LightGBM time-series forecast.

    Features computed ONLY from data at or before each point (no future leakage):
    - Lag features: lag_1, lag_7, lag_14, lag_28
    - Rolling statistics: rolling_mean_7, rolling_mean_14, rolling_std_7
    - Calendar features: day_of_week, day_of_month, week_of_year, month
    - Growth: growth_7d, growth_28d

    Temporal split: 60% train / 20% val / 20% test
    NEVER randomly shuffle.
    """
    try:
        import lightgbm as lgb
        n = len(series)
        if n < MIN_TRAIN_POINTS * 2:
            return exp_smoothing_forecast(series, horizon)

        df = series.reset_index()
        df.columns = ['date', 'cost']
        df['date'] = pd.to_datetime(df['date'])

        # Build lag/rolling features — all computed from past data only
        for lag in [1, 7, 14, 28]:
            df[f'lag_{lag}'] = df['cost'].shift(lag)
        df['rolling_mean_7'] = df['cost'].shift(1).rolling(7).mean()
        df['rolling_mean_14'] = df['cost'].shift(1).rolling(14).mean()
        df['rolling_std_7'] = df['cost'].shift(1).rolling(7).std()
        df['day_of_week'] = df['date'].dt.dayofweek
        df['day_of_month'] = df['date'].dt.day
        df['week_of_year'] = df['date'].dt.isocalendar().week.astype(int)
        df['month'] = df['date'].dt.month
        df['growth_7d'] = df['cost'].shift(1).pct_change(7)
        df['growth_28d'] = df['cost'].shift(1).pct_change(28)

        df = df.dropna()
        if len(df) < 10:
            return exp_smoothing_forecast(series, horizon)

        feature_cols = [
            'lag_1', 'lag_7', 'lag_14', 'lag_28',
            'rolling_mean_7', 'rolling_mean_14', 'rolling_std_7',
            'day_of_week', 'day_of_month', 'week_of_year', 'month',
            'growth_7d', 'growth_28d'
        ]

        # Temporal split (no shuffle)
        n_clean = len(df)
        train_end = int(n_clean * 0.6)
        val_end = int(n_clean * 0.8)

        X_train = df[feature_cols].iloc[:train_end]
        y_train = df['cost'].iloc[:train_end]
        X_val = df[feature_cols].iloc[train_end:val_end]
        y_val = df['cost'].iloc[train_end:val_end]
        X_test = df[feature_cols].iloc[val_end:]
        y_test = df['cost'].iloc[val_end:]

        model = lgb.LGBMRegressor(
            n_estimators=200,
            learning_rate=0.05,
            num_leaves=15,
            random_state=RANDOM_SEED,
            verbose=-1,
        )
        model.fit(X_train, y_train, eval_set=[(X_val, y_val)])

        val_pred = model.predict(X_val)
        metrics = _evaluate(y_val.values, val_pred)

        # Naive baseline comparison (prevent model if not better)
        naive_val = np.full(len(y_val), float(y_train.iloc[-1]))
        naive_metrics = _evaluate(y_val.values, naive_val)
        if metrics['wape'] >= naive_metrics['wape']:
            # LightGBM not better — fall back to exp smoothing
            return exp_smoothing_forecast(series, horizon)

        # Test metrics
        if len(X_test) > 0:
            test_pred = model.predict(X_test)
            test_metrics = _evaluate(y_test.values, test_pred)
        else:
            test_metrics = metrics

        # Recursive forecast
        history = list(series.values)
        forecast_dates = []
        forecast_vals = []
        last_date = series.index[-1]

        for i in range(horizon):
            fdate = last_date + timedelta(days=i + 1)
            n_hist = len(history)
            def safe_get(lag): return history[-lag] if n_hist >= lag else np.nan
            def safe_roll_mean(w): return np.mean(history[-w:]) if n_hist >= w else np.nan
            def safe_roll_std(w): return np.std(history[-w:]) if n_hist >= w else np.nan
            def safe_growth(w): return (history[-1] / history[-w - 1] - 1) if n_hist > w else np.nan

            feat = pd.DataFrame([{
                'lag_1': safe_get(1), 'lag_7': safe_get(7),
                'lag_14': safe_get(14), 'lag_28': safe_get(28),
                'rolling_mean_7': safe_roll_mean(7), 'rolling_mean_14': safe_roll_mean(14),
                'rolling_std_7': safe_roll_std(7),
                'day_of_week': fdate.dayofweek, 'day_of_month': fdate.day,
                'week_of_year': fdate.isocalendar()[1], 'month': fdate.month,
                'growth_7d': safe_growth(7), 'growth_28d': safe_growth(28),
            }])
            pred = max(0, float(model.predict(feat)[0]))
            history.append(pred)
            forecast_dates.append(str(fdate)[:10])
            forecast_vals.append(round(pred, 2))

        points = [ForecastPoint(date=d, predicted_cost=v) for d, v in zip(forecast_dates, forecast_vals)]

        return ForecastResult(
            entity=entity,
            method=ForecastMethod.lightgbm,
            forecast_horizon_days=horizon,
            points=points,
            metrics=metrics,
            baseline_metrics=naive_metrics,
            training_period={
                "train_start": str(df['date'].iloc[0])[:10],
                "train_end": str(df['date'].iloc[train_end - 1])[:10],
                "val_start": str(df['date'].iloc[train_end])[:10],
                "val_end": str(df['date'].iloc[val_end - 1])[:10] if val_end > train_end else "",
                "features": feature_cols,
                "random_seed": RANDOM_SEED,
                "n_estimators": 200,
                "leakage_prevention": "All features computed from data at or before prediction point",
            },
            model_version="lgbm-v1",
            generated_at=datetime.utcnow(),
        )
    except ImportError:
        return exp_smoothing_forecast(series, horizon)
    except Exception:
        return exp_smoothing_forecast(series, horizon)


def forecast_entity(
    dataset_id: str,
    entity_type: str,
    entity_value: str,
    horizon_days: int = 30,
) -> ForecastResult:
    """Forecast spend for a specific entity."""
    from .storage import download_dataset_parquet
    parquet_path = download_dataset_parquet(dataset_id)
    duck = get_duck()

    if entity_type == "total":
        where = ""
    else:
        where = f"WHERE CAST({entity_type} AS VARCHAR) = '{entity_value}'"

    rows = duck.execute(f"""
        SELECT DATE_TRUNC('day', charge_period_start)::DATE as day, SUM(billed_cost) as cost
        FROM read_parquet('{parquet_path}')
        {where}
        GROUP BY DATE_TRUNC('day', charge_period_start)
        ORDER BY day
    """).fetchdf()

    if rows.empty or len(rows) < 5:
        raise ValueError(f"Insufficient data for entity {entity_type}={entity_value}")

    rows['day'] = pd.to_datetime(rows['day'])
    series = rows.set_index('day')['cost'].astype(float)
    entity_label = f"{entity_type}:{entity_value}"

    result = lightgbm_forecast(series, horizon_days, entity=entity_label)
    result.entity = entity_label
    return result


def forecast_total_spend(dataset_id: str, horizon_days: int = 30) -> ForecastResult:
    """Forecast total dataset spend."""
    return forecast_entity(dataset_id, "total", "all", horizon_days)
