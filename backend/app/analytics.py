"""Single-currency analytics with bound values and explicit period comparisons."""

from datetime import date, timedelta

from .query import columns, currency, execute, money, period_filter
from .schemas import (
    CostAttributionReport,
    CostDriver,
    SpendDataPoint,
    SpendSummary,
    SpendTrend,
)


def _get_parquet_path(dataset_id):
    from .storage import download_dataset_parquet

    return str(download_dataset_parquet(dataset_id))


def _column_exists(path, column):
    return column in columns(path)


def _previous_period(path, start=None, end=None):
    lo, hi = execute(
        path, "SELECT MIN(charge_period_start), MAX(charge_period_start) FROM {source}"
    ).fetchone()
    if not lo:
        return None
    start = date.fromisoformat(str(start)) if start else lo.date()
    end = date.fromisoformat(str(end)) if end else hi.date()
    days = (end - start).days + 1
    previous_start, previous_end = (
        start - timedelta(days=days),
        start - timedelta(days=1),
    )
    if previous_start < lo.date():
        return None
    return start, end, previous_start, previous_end


def _change(path, start=None, end=None):
    windows = _previous_period(path, start, end)
    if windows is None:
        return None

    def total(a, b):
        where, args = period_filter(a, b)
        return float(
            execute(
                path, f"SELECT {money('billed_cost')} FROM {{source}}" + where, args
            ).fetchone()[0]
        )

    current = total(*windows[:2])
    previous = total(*windows[2:])
    return round((current - previous) / abs(previous) * 100, 2) if previous else None


def get_resource_breakdown(
    dataset_id, dimension="service", period_start=None, period_end=None, limit=25
):
    path = _get_parquet_path(dataset_id)
    currency(path)
    from .query import dimension as validate

    dim = validate(dimension)
    if not 1 <= limit <= 1000:
        raise ValueError("limit must be between 1 and 1000")
    if dim not in columns(path):
        return []
    where, args = period_filter(period_start, period_end)
    effective = (
        "COALESCE(effective_cost,billed_cost)"
        if "effective_cost" in columns(path)
        else "billed_cost"
    )
    rows = execute(
        path,
        f"SELECT COALESCE(CAST({dim} AS VARCHAR),'unknown'),{money('billed_cost')},{money(effective)},COUNT(*) FROM {{source}}"
        + where
        + f" GROUP BY {dim} ORDER BY 2 DESC,1 LIMIT ?",
        [*args, limit],
    ).fetchall()
    return [
        dict(
            value=r[0],
            billed_cost=round(float(r[1]), 2),
            effective_cost=round(float(r[2]), 2),
            row_count=r[3],
        )
        for r in rows
    ]


def get_spend_summary(dataset_id, period_start=None, period_end=None):
    path = _get_parquet_path(dataset_id)
    unit = currency(path)
    where, args = period_filter(period_start, period_end)
    effective = (
        "COALESCE(effective_cost,billed_cost)"
        if "effective_cost" in columns(path)
        else "billed_cost"
    )
    row = execute(
        path,
        f"SELECT {money('billed_cost')},{money(effective)},MIN(charge_period_start),MAX(charge_period_start) FROM {{source}}"
        + where,
        args,
    ).fetchone()

    def breakdown(dim):
        return {
            r["value"]: r["billed_cost"]
            for r in get_resource_breakdown(dataset_id, dim, period_start, period_end, 1000)
        }

    return SpendSummary(
        period_start=str(row[2])[:10] if row[2] else "",
        period_end=str(row[3])[:10] if row[3] else "",
        total_billed_cost=round(float(row[0]), 2),
        total_effective_cost=round(float(row[1]), 2),
        currency=unit,
        mom_change_pct=_change(path, period_start, period_end),
        provider_breakdown=breakdown("provider"),
        account_breakdown=breakdown("account"),
        service_breakdown=breakdown("service"),
        region_breakdown=breakdown("region"),
    )


def get_spend_trend(dataset_id, granularity="daily", period_start=None, period_end=None):
    path = _get_parquet_path(dataset_id)
    currency(path)
    trunc = {"daily": "day", "weekly": "week", "monthly": "month"}.get(granularity)
    if not trunc:
        raise ValueError("Unsupported granularity")
    where, args = period_filter(period_start, period_end)
    effective = (
        "COALESCE(effective_cost,billed_cost)"
        if "effective_cost" in columns(path)
        else "billed_cost"
    )
    rows = execute(
        path,
        f"SELECT DATE_TRUNC('{trunc}',charge_period_start)::DATE,{money('billed_cost')},{money(effective)} FROM {{source}}"
        + where
        + " GROUP BY 1 ORDER BY 1",
        args,
    ).fetchall()
    points = [
        SpendDataPoint(
            date=str(r[0]),
            billed_cost=round(float(r[1]), 2),
            effective_cost=round(float(r[2]), 2),
        )
        for r in rows
    ]
    return SpendTrend(
        granularity=granularity,
        period_start=points[0].date if points else "",
        period_end=points[-1].date if points else "",
        data_points=points,
    )


def get_cost_drivers(dataset_id, period_start=None, period_end=None, top_n=10):
    path = _get_parquet_path(dataset_id)
    unit = currency(path)
    where, args = period_filter(period_start, period_end)
    total = float(
        execute(path, f"SELECT {money('billed_cost')} FROM {{source}}" + where, args).fetchone()[0]
    )
    drivers = []
    windows = _previous_period(path, period_start, period_end)
    for dim in ["provider", "account", "service", "region"]:
        rows = get_resource_breakdown(dataset_id, dim, period_start, period_end, 1000)
        previous = (
            {
                r["value"]: r["billed_cost"]
                for r in get_resource_breakdown(dataset_id, dim, *windows[2:], 1000)
            }
            if windows
            else {}
        )
        for row in rows:
            cost = row["billed_cost"]
            prev = previous.get(row["value"])
            drivers.append(
                CostDriver(
                    dimension=dim,
                    value=row["value"],
                    cost=cost,
                    share_pct=round(cost / total * 100, 2) if total else 0,
                    change_pct=round((cost - prev) / abs(prev) * 100, 2) if prev else None,
                )
            )
    if "service" in columns(path):
        positives = execute(
            path,
            "SELECT service,SUM(CASE WHEN billed_cost>0 THEN billed_cost ELSE 0 END) FROM {source}"
            + where
            + " GROUP BY service",
            args,
        ).fetchall()
        gross = sum(float(r[1]) for r in positives)
        hhi = sum((float(r[1]) / gross) ** 2 for r in positives) if gross else 0
    else:
        hhi = 0
    drivers.sort(key=lambda d: (-d.cost, d.dimension, d.value))
    return CostAttributionReport(
        dataset_id=dataset_id,
        period_start=str(period_start or ""),
        period_end=str(period_end or ""),
        top_drivers=drivers[:top_n],
        total_cost=round(total, 2),
        concentration_score=round(hhi, 4),
        period_over_period_change_pct=_change(path, period_start, period_end),
        evidence=[
            f"Net billed spend: {unit} {total:.2f}",
            f"Service HHI on positive gross spend: {hhi:.4f}",
            "Period comparison uses equal-length adjacent calendar windows; unavailable without preceding coverage.",
        ],
    )
