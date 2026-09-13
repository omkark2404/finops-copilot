"""
Deterministic Cost Analytics.

All numerical results computed via DuckDB SQL against canonical Parquet files.
No LLM involvement in any calculation.
"""
from __future__ import annotations
import math
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import duckdb
import pandas as pd

from .config import get_settings
from .schemas import (
    CostAttributionReport, CostDriver,
    SpendDataPoint, SpendSummary, SpendTrend
)


def _get_parquet_path(dataset_id: str) -> str:
    """
    Resolve the local path for a dataset's Parquet file.

    For STORAGE_BACKEND=local: returns the direct local path.
    For STORAGE_BACKEND=r2: downloads from R2 to a temp file and returns that path.

    Raises FileNotFoundError("DATASET_STORAGE_MISSING: ...") if the file is missing.
    Raises RuntimeError on other storage errors.
    """
    from .storage import download_dataset_parquet
    local_path = download_dataset_parquet(dataset_id)
    return str(local_path)


def _duck() -> duckdb.DuckDBPyConnection:
    from .db import get_duck
    return get_duck()


def get_spend_summary(
    dataset_id: str,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
) -> SpendSummary:
    """Total spend with provider/account/service/region breakdowns."""
    parquet_path = _get_parquet_path(dataset_id)
    duck = _duck()

    where_clause = ""
    if period_start and period_end:
        where_clause = f"WHERE charge_period_start >= '{period_start}' AND charge_period_start <= '{period_end}'"
    elif period_start:
        where_clause = f"WHERE charge_period_start >= '{period_start}'"
    elif period_end:
        where_clause = f"WHERE charge_period_start <= '{period_end}'"

    totals = duck.execute(f"""
        SELECT
            COALESCE(SUM(billed_cost), 0) as total_billed,
            COALESCE(SUM(effective_cost), 0) as total_effective,
            MIN(charge_period_start) as period_min,
            MAX(charge_period_start) as period_max,
            MODE() WITHIN GROUP (ORDER BY currency) as currency
        FROM read_parquet('{parquet_path}')
        {where_clause}
    """).fetchone()

    total_billed = float(totals[0] or 0)
    total_effective = float(totals[1] or 0)
    actual_start = str(totals[2])[:10] if totals[2] else (period_start or "")
    actual_end = str(totals[3])[:10] if totals[3] else (period_end or "")
    currency = str(totals[4] or "USD")

    def breakdown(dimension: str) -> dict[str, float]:
        if not _column_exists(parquet_path, dimension):
            return {}
        rows = duck.execute(f"""
            SELECT
                COALESCE(CAST({dimension} AS VARCHAR), 'unknown') as dim,
                SUM(billed_cost) as cost
            FROM read_parquet('{parquet_path}')
            {where_clause}
            GROUP BY {dimension}
            ORDER BY cost DESC
            LIMIT 20
        """).fetchall()
        return {r[0]: round(float(r[1] or 0), 2) for r in rows}

    # Calculate MoM change
    mom_pct = _compute_mom_change(parquet_path, duck, period_start, period_end)

    return SpendSummary(
        period_start=actual_start,
        period_end=actual_end,
        total_billed_cost=round(total_billed, 2),
        total_effective_cost=round(total_effective, 2),
        currency=currency,
        mom_change_pct=mom_pct,
        provider_breakdown=breakdown("provider"),
        account_breakdown=breakdown("account"),
        service_breakdown=breakdown("service"),
        region_breakdown=breakdown("region"),
    )


def _column_exists(parquet_path: str, column: str) -> bool:
    duck = _duck()
    try:
        result = duck.execute(f"SELECT {column} FROM read_parquet('{parquet_path}') LIMIT 0").fetchall()
        return True
    except Exception:
        return False


def _compute_mom_change(parquet_path: str, duck, period_start, period_end) -> Optional[float]:
    """Compute month-over-month cost change."""
    try:
        rows = duck.execute(f"""
            SELECT
                DATE_TRUNC('month', charge_period_start) as month,
                SUM(billed_cost) as cost
            FROM read_parquet('{parquet_path}')
            GROUP BY DATE_TRUNC('month', charge_period_start)
            ORDER BY month DESC
            LIMIT 2
        """).fetchall()
        if len(rows) >= 2:
            current = float(rows[0][1] or 0)
            prior = float(rows[1][1] or 0)
            if prior > 0:
                return round((current - prior) / prior * 100, 2)
    except Exception:
        pass
    return None


def get_spend_trend(
    dataset_id: str,
    granularity: str = "daily",
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
) -> SpendTrend:
    """Time-series spend trend at daily/weekly/monthly granularity."""
    parquet_path = _get_parquet_path(dataset_id)
    duck = _duck()

    trunc_map = {"daily": "day", "weekly": "week", "monthly": "month"}
    trunc = trunc_map.get(granularity, "day")

    where_clause = ""
    if period_start and period_end:
        where_clause = f"WHERE charge_period_start >= '{period_start}' AND charge_period_start <= '{period_end}'"

    rows = duck.execute(f"""
        SELECT
            DATE_TRUNC('{trunc}', charge_period_start)::DATE as period,
            SUM(billed_cost) as billed,
            COALESCE(SUM(effective_cost), SUM(billed_cost)) as effective
        FROM read_parquet('{parquet_path}')
        {where_clause}
        GROUP BY DATE_TRUNC('{trunc}', charge_period_start)
        ORDER BY period
    """).fetchall()

    data_points = [
        SpendDataPoint(
            date=str(r[0])[:10],
            billed_cost=round(float(r[1] or 0), 2),
            effective_cost=round(float(r[2] or 0), 2),
        )
        for r in rows
    ]

    return SpendTrend(
        granularity=granularity,
        period_start=data_points[0].date if data_points else "",
        period_end=data_points[-1].date if data_points else "",
        data_points=data_points,
    )


def get_cost_drivers(
    dataset_id: str,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
    top_n: int = 10,
) -> CostAttributionReport:
    """Identify top cost drivers across all dimensions."""
    parquet_path = _get_parquet_path(dataset_id)
    duck = _duck()

    where_clause = ""
    if period_start and period_end:
        where_clause = f"WHERE charge_period_start >= '{period_start}' AND charge_period_start <= '{period_end}'"

    total_result = duck.execute(f"""
        SELECT COALESCE(SUM(billed_cost), 0)
        FROM read_parquet('{parquet_path}')
        {where_clause}
    """).fetchone()
    total_cost = float(total_result[0] or 0)

    drivers = []
    for dim in ["provider", "account", "service", "region"]:
        if not _column_exists(parquet_path, dim):
            continue
        rows = duck.execute(f"""
            SELECT
                COALESCE(CAST({dim} AS VARCHAR), 'unknown') as val,
                SUM(billed_cost) as cost
            FROM read_parquet('{parquet_path}')
            {where_clause}
            GROUP BY {dim}
            ORDER BY cost DESC
            LIMIT {top_n}
        """).fetchall()
        for r in rows:
            cost = float(r[1] or 0)
            share = (cost / total_cost * 100) if total_cost > 0 else 0
            drivers.append(CostDriver(
                dimension=dim,
                value=str(r[0]),
                cost=round(cost, 2),
                share_pct=round(share, 2),
            ))

    # Sort by cost descending, take top N
    drivers.sort(key=lambda d: d.cost, reverse=True)
    top_drivers = drivers[:top_n]

    # Concentration (HHI): sum of squared market shares
    if top_drivers and total_cost > 0:
        shares = [d.cost / total_cost for d in top_drivers]
        hhi = sum(s * s for s in shares)
    else:
        hhi = 0.0

    # PoP change
    pop_change = _compute_mom_change(parquet_path, duck, period_start, period_end)

    evidence = [
        f"Total spend in period: ${total_cost:,.2f}",
        f"Top cost driver: {top_drivers[0].value} ({top_drivers[0].dimension}) at ${top_drivers[0].cost:,.2f}" if top_drivers else "",
        f"Cost concentration (HHI): {hhi:.3f}",
    ]

    return CostAttributionReport(
        dataset_id=dataset_id,
        period_start=period_start or "",
        period_end=period_end or "",
        top_drivers=top_drivers,
        total_cost=round(total_cost, 2),
        concentration_score=round(hhi, 4),
        period_over_period_change_pct=pop_change,
        evidence=[e for e in evidence if e],
    )


def get_resource_breakdown(
    dataset_id: str,
    dimension: str,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
    limit: int = 25,
) -> list[dict]:
    """Breakdown by any canonical dimension."""
    parquet_path = _get_parquet_path(dataset_id)
    duck = _duck()

    valid_dims = {"provider", "account", "sub_account", "service", "category", "resource", "region", "sku", "charge_category"}
    if dimension not in valid_dims:
        raise ValueError(f"Invalid dimension: {dimension}. Must be one of {valid_dims}")

    if not _column_exists(parquet_path, dimension):
        return []

    where_clause = ""
    if period_start and period_end:
        where_clause = f"WHERE charge_period_start >= '{period_start}' AND charge_period_start <= '{period_end}'"

    rows = duck.execute(f"""
        SELECT
            COALESCE(CAST({dimension} AS VARCHAR), 'unknown') as val,
            SUM(billed_cost) as cost,
            COALESCE(SUM(effective_cost), SUM(billed_cost)) as effective_cost,
            COUNT(*) as row_count
        FROM read_parquet('{parquet_path}')
        {where_clause}
        GROUP BY {dimension}
        ORDER BY cost DESC
        LIMIT {limit}
    """).fetchall()

    return [
        {"value": r[0], "billed_cost": round(float(r[1] or 0), 2),
         "effective_cost": round(float(r[2] or 0), 2), "row_count": int(r[3])}
        for r in rows
    ]

