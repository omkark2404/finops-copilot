"""Application lifecycle, session request protection and bounded request rates."""

import logging
import uuid
from collections import OrderedDict, deque
from contextlib import asynccontextmanager
from time import monotonic

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api import router
from .auth import hash_password
from .body_limit import BodyLimitMiddleware
from .config import get_settings
from .db import close_db, init_db


@asynccontextmanager
async def lifespan(app):
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    await init_db()
    await _ensure_admin_user()
    try:
        yield
    finally:
        await close_db()


async def _ensure_admin_user():
    from sqlalchemy import select

    from .db import get_session_factory
    from .models import User

    settings = get_settings()
    async with get_session_factory()() as session:
        if not (
            await session.execute(select(User).where(User.email == settings.admin_email))
        ).scalar_one_or_none():
            session.add(
                User(
                    id=str(uuid.uuid4()),
                    email=settings.admin_email,
                    hashed_password=hash_password(settings.admin_password),
                    role="ADMIN",
                    is_active=True,
                )
            )
            await session.commit()


app = FastAPI(
    title="FinOps Copilot",
    description="Portfolio prototype for FOCUS billing analytics and optional Gemini explanations",
    version="0.2.0",
    lifespan=lifespan,
)
settings = get_settings()
app.add_middleware(BodyLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-FinOps-Client"],
)
_buckets = OrderedDict()


@app.middleware("http")
async def request_controls(request: Request, call_next):
    request_id = str(uuid.uuid4())
    unsafe = request.method in {"POST", "PUT", "PATCH", "DELETE"}
    # Custom header + exact Origin checks protect cross-site cookies from CSRF.
    if unsafe and request.cookies.get("finops_session"):
        origin = request.headers.get("origin")
        if request.headers.get("X-FinOps-Client") != "1" or (
            origin and origin not in settings.cors_origins_list
        ):
            return JSONResponse({"detail": "Invalid session request origin"}, status_code=403)
    if request.url.path not in {"/health", "/live"} and settings.app_env != "test":
        key = (
            request.client.host if request.client else "unknown",
            "login" if request.url.path == "/auth/login" else "requests",
        )
        now = monotonic()
        bucket = _buckets.setdefault(key, deque())
        while bucket and bucket[0] < now - 60:
            bucket.popleft()
        limit = 10 if key[1] == "login" else 120
        if len(bucket) >= limit:
            return JSONResponse(
                {"detail": "Rate limit reached"},
                status_code=429,
                headers={"Retry-After": "60"},
            )
        bucket.append(now)
        _buckets.move_to_end(key)
        while len(_buckets) > 10000:
            _buckets.popitem(last=False)
    with structlog.contextvars.bound_contextvars(request_id=request_id):
        response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    return response


app.include_router(router)
