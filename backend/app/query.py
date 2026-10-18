"""Bound Parquet queries and inclusive calendar-date filters."""

import re
from datetime import date, datetime, timedelta

from .db import get_duck

DIMENSIONS = {
    "provider",
    "account",
    "sub_account",
    "service",
    "category",
    "resource",
    "region",
    "sku",
    "charge_category",
}


def dimension(value):
    if value not in DIMENSIONS:
        raise ValueError("Unsupported grouping dimension")
    return value


def period_filter(start=None, end=None):
    def parse(value):
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("Dates must use YYYY-MM-DD")
        return date.fromisoformat(value)

    start = parse(start) if start else None
    end = parse(end) if end else None
    if start and end and start > end:
        raise ValueError("period_start must not exceed period_end")
    clauses, args = [], []
    if start:
        clauses.append("charge_period_start >= ?")
        args.append(start)
    if end == date.max:
        raise ValueError("End date is out of supported range")
    if end:
        clauses.append("charge_period_start < ?")
        args.append(end + timedelta(days=1))
    return (" WHERE " + " AND ".join(clauses) if clauses else ""), args


def execute(path, sql, args=()):
    return get_duck().execute(sql.replace("{source}", "read_parquet(?)"), [str(path), *args])


def columns(path):
    return {row[0] for row in execute(path, "DESCRIBE SELECT * FROM {source}").fetchall()}


def currency(path):
    rows = execute(path, "SELECT DISTINCT currency FROM {source}").fetchall()
    if len(rows) != 1 or not rows[0][0]:
        raise ValueError("Exactly one nonempty billing currency is required")
    return str(rows[0][0])


def money(expression):
    return f"COALESCE(SUM(CAST({expression} AS DECIMAL(28,8))), 0)"
