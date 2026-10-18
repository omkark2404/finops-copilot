"""Causal historical anomaly flags; scores are heuristics, not probabilities."""

import uuid

import numpy as np
import pandas as pd

from .query import currency, dimension, execute
from .schemas import AnomalyDetail, AnomalyMethod, AnomalyReport, AnomalySeverity


def classify_severity(deviation_pct):
    value = abs(deviation_pct)
    return (
        AnomalySeverity.low
        if value < 25
        else AnomalySeverity.medium
        if value < 50
        else AnomalySeverity.high
        if value < 100
        else AnomalySeverity.critical
    )


def _detect(series, entity_type, entity_value, dataset_id, method, window=14, threshold=3):
    if len(series) < 8:
        return []
    series = series.sort_index().astype(float)
    history = series.shift(1)
    if method == "robust_zscore":
        expected = history.rolling(28, min_periods=7).median()
        scale = (
            history.rolling(28, min_periods=7).apply(
                lambda x: np.nanmedian(np.abs(x - np.nanmedian(x))), raw=True
            )
            / 0.6745
        )
    elif method == "ewma":
        expected = history.ewm(span=window, min_periods=7, adjust=False).mean()
        scale = history.ewm(span=window, min_periods=7, adjust=False).std()
    else:
        expected = history.rolling(window, min_periods=7).mean()
        scale = history.rolling(window, min_periods=7).std()
    result = []
    for index in series.index:
        actual = float(series.loc[index])
        baseline = float(expected.loc[index])
        spread = float(scale.loc[index])
        if not np.isfinite(baseline) or not np.isfinite(spread):
            continue
        delta = actual - baseline
        score = (
            delta / spread
            if spread > 1e-9
            else (threshold * 2 * np.sign(delta) if abs(delta) > 1e-6 else 0)
        )
        if abs(score) < threshold:
            continue
        pct = delta / abs(baseline) * 100 if baseline else (100.0 * np.sign(delta) if delta else 0)
        result.append(
            AnomalyDetail(
                id=str(uuid.uuid4()),
                dataset_id=dataset_id,
                entity_type=entity_type,
                entity_value=entity_value,
                detected_at=str(index)[:10],
                actual_cost=round(actual, 2),
                expected_cost=round(baseline, 2),
                deviation=round(delta, 2),
                deviation_pct=round(pct, 2),
                severity=classify_severity(pct),
                method=AnomalyMethod(method),
                confidence=round(min(0.99, abs(score) / (threshold * 2)), 3),
                supporting_evidence=[
                    f"Actual billed amount: {actual:.2f}",
                    f"Prior-observation baseline: {baseline:.2f}",
                    f"Deviation: {delta:.2f} ({pct:.1f}%); heuristic score: {score:.2f}",
                    "No observations at or after this date were used for the baseline; an alert is not confirmed waste.",
                ],
            )
        )
    return result


def detect_robust_zscore(series, entity_type, entity_value, dataset_id, threshold=3.5):
    return _detect(
        series,
        entity_type,
        entity_value,
        dataset_id,
        "robust_zscore",
        threshold=threshold,
    )


def detect_rolling_zscore(series, entity_type, entity_value, dataset_id, window=14, threshold=3):
    return _detect(
        series,
        entity_type,
        entity_value,
        dataset_id,
        "rolling_zscore",
        window,
        threshold,
    )


def detect_ewma(series, entity_type, entity_value, dataset_id, span=14, threshold=3):
    return _detect(series, entity_type, entity_value, dataset_id, "ewma", span, threshold)


def _load_entity_series(dataset_id, entity_type, entity_value):
    from .storage import download_dataset_parquet

    path = download_dataset_parquet(dataset_id)
    currency(path)
    if entity_type == "total":
        where, args = "", []
    else:
        where, args = (
            f" WHERE CAST({dimension(entity_type)} AS VARCHAR)=?",
            [entity_value],
        )
    rows = execute(
        path,
        "SELECT DATE_TRUNC('day',charge_period_start)::DATE AS day,SUM(billed_cost) AS cost FROM {source}"
        + where
        + " GROUP BY 1 ORDER BY 1",
        args,
    ).fetchdf()
    return pd.Series(
        rows["cost"].values,
        index=pd.DatetimeIndex(pd.to_datetime(rows["day"])),
        dtype=float,
    )


def run_anomaly_detection(dataset_id, entity_type="service"):
    from .storage import download_dataset_parquet

    path = download_dataset_parquet(dataset_id)
    currency(path)
    dim = dimension(entity_type)
    entities = execute(
        path,
        f"SELECT DISTINCT CAST({dim} AS VARCHAR) FROM {{source}} WHERE {dim} IS NOT NULL ORDER BY 1",
    ).fetchall()
    if len(entities) > 1000:
        raise ValueError("More than 1000 entities: upload a smaller analytical scope")
    anomalies = []
    for (entity,) in entities:
        series = _load_entity_series(dataset_id, dim, entity)
        primary = detect_robust_zscore(series, dim, entity, dataset_id)
        seen = {a.detected_at for a in primary}
        anomalies.extend(
            primary
            + [a for a in detect_ewma(series, dim, entity, dataset_id) if a.detected_at not in seen]
        )
    anomalies.sort(key=lambda a: (-abs(a.deviation), a.entity_value, a.detected_at))
    low, high = execute(
        path, "SELECT MIN(charge_period_start),MAX(charge_period_start) FROM {source}"
    ).fetchone()
    return AnomalyReport(
        dataset_id=dataset_id,
        period_start=str(low)[:10] if low else "",
        period_end=str(high)[:10] if high else "",
        anomalies=anomalies,
        total_anomalies=len(anomalies),
        critical_count=sum(a.severity == AnomalySeverity.critical for a in anomalies),
        high_count=sum(a.severity == AnomalySeverity.high for a in anomalies),
    )
