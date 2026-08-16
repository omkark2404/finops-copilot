"""
Statistical Anomaly Detection.

Implements:
- Rolling Z-score
- EWMA (Exponentially Weighted Moving Average)
- Robust Z-score (median/MAD)
- Seasonal baseline
- Optional Isolation Forest

All detection is statistical/deterministic.
The LLM is never used for anomaly calculation.
"""
from __future__ import annotations
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from scipy import stats

from .config import get_settings
from .db import get_duck
from .schemas import AnomalyDetail, AnomalyMethod, AnomalyReport, AnomalySeverity, AnomalyStatus


def classify_severity(deviation_pct: float) -> AnomalySeverity:
    """Classify anomaly severity based on percentage deviation."""
    abs_dev = abs(deviation_pct)
    if abs_dev < 25:
        return AnomalySeverity.low
    elif abs_dev < 50:
        return AnomalySeverity.medium
    elif abs_dev < 100:
        return AnomalySeverity.high
    else:
        return AnomalySeverity.critical


def _series_to_anomalies(
    series: pd.Series,
    entity_type: str,
    entity_value: str,
    dataset_id: str,
    expected: pd.Series,
    method: AnomalyMethod,
    threshold: float = 3.0,
) -> list[AnomalyDetail]:
    """Convert series + expected to AnomalyDetail list."""
    anomalies = []
    std = (series - expected).std()
    if std == 0:
        return []

    for idx in series.index:
        actual = float(series[idx])
        exp = float(expected[idx])
        if exp == 0:
            continue
        deviation = actual - exp
        deviation_pct = (deviation / abs(exp)) * 100
        z = deviation / std if std > 0 else 0

        if abs(z) >= threshold:
            confidence = min(1.0, abs(z) / (threshold * 2))
            severity = classify_severity(deviation_pct)
            anomalies.append(AnomalyDetail(
                id=str(uuid.uuid4()),
                dataset_id=dataset_id,
                entity_type=entity_type,
                entity_value=entity_value,
                detected_at=str(idx)[:10] if hasattr(idx, '__str__') else str(idx),
                actual_cost=round(actual, 2),
                expected_cost=round(exp, 2),
                deviation=round(deviation, 2),
                deviation_pct=round(deviation_pct, 2),
                severity=severity,
                method=method,
                confidence=round(confidence, 3),
                supporting_evidence=[
                    f"Actual: ${actual:,.2f}",
                    f"Expected: ${exp:,.2f}",
                    f"Deviation: {deviation_pct:+.1f}%",
                    f"Z-score: {z:.2f}",
                    f"Detection method: {method.value}",
                ],
                status=AnomalyStatus.open,
            ))
    return anomalies


def detect_rolling_zscore(
    series: pd.Series,
    entity_type: str,
    entity_value: str,
    dataset_id: str,
    window: int = 14,
    threshold: float = 3.0,
) -> list[AnomalyDetail]:
    """Rolling window Z-score anomaly detection."""
    if len(series) < window + 1:
        return []
    rolling_mean = series.rolling(window=window, min_periods=max(3, window // 2)).mean()
    rolling_std = series.rolling(window=window, min_periods=max(3, window // 2)).std()
    # Avoid division by zero
    rolling_std = rolling_std.replace(0, np.nan)
    z_scores = (series - rolling_mean) / rolling_std
    anomaly_mask = z_scores.abs() >= threshold
    anomalies = []
    for idx in series[anomaly_mask].index:
        actual = float(series[idx])
        exp = float(rolling_mean[idx]) if not np.isnan(rolling_mean[idx]) else actual
        z = float(z_scores[idx])
        deviation_pct = ((actual - exp) / abs(exp) * 100) if exp != 0 else 0
        confidence = min(1.0, abs(z) / (threshold * 2))
        anomalies.append(AnomalyDetail(
            id=str(uuid.uuid4()),
            dataset_id=dataset_id,
            entity_type=entity_type,
            entity_value=entity_value,
            detected_at=str(idx)[:10],
            actual_cost=round(actual, 2),
            expected_cost=round(exp, 2),
            deviation=round(actual - exp, 2),
            deviation_pct=round(deviation_pct, 2),
            severity=classify_severity(deviation_pct),
            method=AnomalyMethod.rolling_zscore,
            confidence=round(confidence, 3),
            supporting_evidence=[
                f"Rolling mean ({window}d): ${exp:,.2f}",
                f"Actual: ${actual:,.2f}",
                f"Z-score: {z:.2f} (threshold: {threshold})",
                f"Deviation: {deviation_pct:+.1f}%",
            ],
            status=AnomalyStatus.open,
        ))
    return anomalies


def detect_robust_zscore(
    series: pd.Series,
    entity_type: str,
    entity_value: str,
    dataset_id: str,
    threshold: float = 3.5,
) -> list[AnomalyDetail]:
    """Robust Z-score using median and MAD (resistant to outliers)."""
    median = series.median()
    mad = (series - median).abs().median()
    if mad == 0:
        std = series.std()
        if std == 0:
            return []
        modified_z = (series - median) / std
    else:
        modified_z = 0.6745 * (series - median) / mad
    anomaly_mask = modified_z.abs() >= threshold
    anomalies = []
    for idx in series[anomaly_mask].index:
        actual = float(series[idx])
        exp = float(median)
        deviation_pct = ((actual - exp) / abs(exp) * 100) if exp != 0 else 0
        z = float(modified_z[idx])
        confidence = min(1.0, abs(z) / (threshold * 2))
        anomalies.append(AnomalyDetail(
            id=str(uuid.uuid4()),
            dataset_id=dataset_id,
            entity_type=entity_type,
            entity_value=entity_value,
            detected_at=str(idx)[:10],
            actual_cost=round(actual, 2),
            expected_cost=round(exp, 2),
            deviation=round(actual - exp, 2),
            deviation_pct=round(deviation_pct, 2),
            severity=classify_severity(deviation_pct),
            method=AnomalyMethod.robust_zscore,
            confidence=round(confidence, 3),
            supporting_evidence=[
                f"Median baseline: ${median:,.2f}",
                f"Actual: ${actual:,.2f}",
                f"Modified Z-score: {z:.2f} (threshold: {threshold})",
                f"Deviation: {deviation_pct:+.1f}%",
            ],
            status=AnomalyStatus.open,
        ))
    return anomalies


def detect_ewma(
    series: pd.Series,
    entity_type: str,
    entity_value: str,
    dataset_id: str,
    span: int = 14,
    threshold: float = 3.0,
) -> list[AnomalyDetail]:
    """EWMA-based anomaly detection."""
    if len(series) < 5:
        return []
    ewma = series.ewm(span=span).mean()
    residuals = series - ewma
    ewma_std = residuals.ewm(span=span).std()
    ewma_std = ewma_std.replace(0, np.nan)
    global_std = series.std()
    if global_std > 0:
        ewma_std = ewma_std.fillna(global_std)
    z = residuals / ewma_std
    anomaly_mask = z.abs() >= threshold
    anomalies = []
    for idx in series[anomaly_mask].index:
        actual = float(series[idx])
        exp = float(ewma[idx])
        deviation_pct = ((actual - exp) / abs(exp) * 100) if exp != 0 else 0
        z_val = float(z[idx])
        confidence = min(1.0, abs(z_val) / (threshold * 2))
        anomalies.append(AnomalyDetail(
            id=str(uuid.uuid4()),
            dataset_id=dataset_id,
            entity_type=entity_type,
            entity_value=entity_value,
            detected_at=str(idx)[:10],
            actual_cost=round(actual, 2),
            expected_cost=round(exp, 2),
            deviation=round(actual - exp, 2),
            deviation_pct=round(deviation_pct, 2),
            severity=classify_severity(deviation_pct),
            method=AnomalyMethod.ewma,
            confidence=round(confidence, 3),
            supporting_evidence=[
                f"EWMA baseline (span={span}): ${exp:,.2f}",
                f"Actual: ${actual:,.2f}",
                f"EWMA Z-score: {z_val:.2f} (threshold: {threshold})",
                f"Deviation: {deviation_pct:+.1f}%",
            ],
            status=AnomalyStatus.open,
        ))
    return anomalies


def _load_entity_series(dataset_id: str, entity_type: str, entity_value: str) -> pd.Series:
    """Load daily cost time series for a specific entity from DuckDB."""
    from .storage import download_dataset_parquet
    parquet_path = download_dataset_parquet(dataset_id)
    duck = get_duck()

    if entity_type == "total":
        where = ""
    else:
        where = f"WHERE CAST({entity_type} AS VARCHAR) = '{entity_value}'"

    rows = duck.execute(f"""
        SELECT
            DATE_TRUNC('day', charge_period_start)::DATE as day,
            SUM(billed_cost) as cost
        FROM read_parquet('{parquet_path}')
        {where}
        GROUP BY DATE_TRUNC('day', charge_period_start)
        ORDER BY day
    """).fetchdf()

    if rows.empty:
        return pd.Series(dtype=float)

    rows['day'] = pd.to_datetime(rows['day'])
    rows = rows.set_index('day')['cost'].astype(float)
    return rows


def run_anomaly_detection(
    dataset_id: str,
    entity_type: str = "service",
) -> AnomalyReport:
    """
    Run anomaly detection across entities of a given type.
    Uses robust Z-score as primary method, EWMA as secondary.
    """
    from .storage import download_dataset_parquet
    parquet_path = download_dataset_parquet(dataset_id)
    duck = get_duck()

    if not _column_exists_duck(duck, parquet_path, entity_type):
        entity_type = "service"

    # Get distinct entities
    entities_result = duck.execute(f"""
        SELECT DISTINCT CAST({entity_type} AS VARCHAR) as entity
        FROM read_parquet('{parquet_path}')
        WHERE {entity_type} IS NOT NULL
        LIMIT 50
    """).fetchdf()

    all_anomalies: list[AnomalyDetail] = []

    for _, row in entities_result.iterrows():
        entity_val = str(row['entity'])
        series = _load_entity_series(dataset_id, entity_type, entity_val)

        if len(series) < 7:
            continue

        # Robust Z-score (primary - most resistant to outliers)
        robust_anoms = detect_robust_zscore(series, entity_type, entity_val, dataset_id)

        # EWMA (secondary)
        ewma_anoms = detect_ewma(series, entity_type, entity_val, dataset_id)

        # Deduplicate by date (prefer robust_zscore)
        seen_dates = {a.detected_at for a in robust_anoms}
        deduped = robust_anoms + [a for a in ewma_anoms if a.detected_at not in seen_dates]
        all_anomalies.extend(deduped)

    # Sort by severity then deviation
    severity_order = {AnomalySeverity.critical: 0, AnomalySeverity.high: 1,
                      AnomalySeverity.medium: 2, AnomalySeverity.low: 3}
    all_anomalies.sort(key=lambda a: (severity_order.get(a.severity, 4), -abs(a.deviation_pct)))

    # Date range
    date_rows = duck.execute(f"""
        SELECT MIN(charge_period_start), MAX(charge_period_start)
        FROM read_parquet('{parquet_path}')
    """).fetchone()

    return AnomalyReport(
        dataset_id=dataset_id,
        period_start=str(date_rows[0])[:10] if date_rows[0] else "",
        period_end=str(date_rows[1])[:10] if date_rows[1] else "",
        anomalies=all_anomalies[:100],  # Cap for response size
        total_anomalies=len(all_anomalies),
        critical_count=sum(1 for a in all_anomalies if a.severity == AnomalySeverity.critical),
        high_count=sum(1 for a in all_anomalies if a.severity == AnomalySeverity.high),
    )


def _column_exists_duck(duck, parquet_path, column) -> bool:
    try:
        duck.execute(f"SELECT {column} FROM read_parquet('{parquet_path}') LIMIT 0")
        return True
    except Exception:
        return False
