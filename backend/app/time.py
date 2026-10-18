"""Metadata timestamps are naive UTC to match the existing SQL schema."""

from datetime import UTC, datetime


def utcnow():
    return datetime.now(UTC).replace(tzinfo=None)
