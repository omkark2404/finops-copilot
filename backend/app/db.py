"""
Database setup for CloudSpend Intelligence.
- PostgreSQL (async SQLAlchemy) for application state
- DuckDB for analytical queries on billing data
"""
from __future__ import annotations
import os
import threading
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import AsyncGenerator

import duckdb
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import get_settings


class Base(DeclarativeBase):
    pass


_engine = None
_session_factory = None
_duck_lock = threading.Lock()
_duck_conn = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        url = settings.database_url
        kwargs = {
            "echo": (settings.app_env == "development"),
        }
        if "sqlite" in url:
            kwargs["connect_args"] = {"check_same_thread": False}
        else:
            kwargs["pool_pre_ping"] = True
        _engine = create_async_engine(url, **kwargs)
    return _engine


def get_session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(), expire_on_commit=False, class_=AsyncSession
        )
    return _session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions."""
    async with get_session_factory()() as session:
        yield session


def get_duck() -> duckdb.DuckDBPyConnection:
    """Thread-safe DuckDB connection (singleton)."""
    global _duck_conn
    with _duck_lock:
        if _duck_conn is None:
            from .storage import get_duckdb_path
            duck_path = str(get_duckdb_path())
            try:
                _duck_conn = duckdb.connect(duck_path)
            except duckdb.IOException:
                _duck_conn = duckdb.connect(duck_path, read_only=True)
        return _duck_conn


async def init_db() -> None:
    """Create all tables and ensure required directories exist."""
    from . import models  # noqa: F401 - ensures models are registered
    from .storage import get_parquet_dir, get_duckdb_path

    get_parquet_dir()
    get_duckdb_path().parent.mkdir(parents=True, exist_ok=True)

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
