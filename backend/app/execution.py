"""Bounded, serialized analytical work for the documented single-process prototype."""

import asyncio
from threading import RLock

from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool

_gate = asyncio.Semaphore(1)
_compute_lock = RLock()


async def compute(function, *args, **kwargs):
    try:
        await asyncio.wait_for(_gate.acquire(), timeout=2)
    except TimeoutError:
        raise HTTPException(503, "Analysis capacity is busy; retry shortly")
    try:

        def guarded():
            with _compute_lock:
                return function(*args, **kwargs)

        return await run_in_threadpool(guarded)
    finally:
        _gate.release()
