"""Metadata sessions and per-thread in-memory analytical connections."""

from collections.abc import AsyncGenerator
from threading import Lock, local

import duckdb
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import get_settings


class Base(DeclarativeBase):
    pass


_engine = None
_session_factory = None
_connections = []
_connection_lock = Lock()
_thread = local()


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    return _engine


def get_session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with get_session_factory()() as session:
        yield session


def get_duck():
    if not hasattr(_thread, "connection"):
        conn = duckdb.connect(":memory:")
        conn.execute("SET TimeZone='UTC'")
        conn.execute("SET threads=2")
        conn.execute("SET memory_limit='512MB'")
        _thread.connection = conn
        with _connection_lock:
            _connections.append(conn)
    return _thread.connection


async def init_db():
    import asyncio

    from .migrate import upgrade
    from .storage import get_data_dir

    get_data_dir()
    await asyncio.to_thread(upgrade)


async def close_db():
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = _session_factory = None
    with _connection_lock:
        for connection in _connections:
            connection.close()
        _connections.clear()
    if hasattr(_thread, "connection"):
        del _thread.connection
