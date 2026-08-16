"""
CloudSpend Intelligence — FastAPI Application Entry Point.
"""
from __future__ import annotations
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api import router
from .auth import hash_password
from .config import get_settings
from .db import init_db

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(__import__('logging'), settings.log_level, 20)
        )
    )
    log.info("Starting CloudSpend Intelligence", version=settings.version, env=settings.app_env)
    await init_db()
    await _ensure_admin_user()
    log.info("Startup complete")
    yield
    log.info("Shutting down")


async def _ensure_admin_user():
    """Create default admin user on first run if it does not exist."""
    from .db import get_session_factory
    from .models import User
    from sqlalchemy import select
    import uuid

    settings = get_settings()
    async with get_session_factory()() as session:
        result = await session.execute(select(User).where(User.email == settings.admin_email))
        if not result.scalar_one_or_none():
            admin = User(
                id=str(uuid.uuid4()),
                email=settings.admin_email,
                hashed_password=hash_password(settings.admin_password),
                role="ADMIN",
                is_active=True,
            )
            session.add(admin)
            await session.commit()
            log.info("Created default admin user", email=settings.admin_email)


app = FastAPI(
    title="CloudSpend Intelligence",
    description="FinOps / Cloud Cost Decision-Intelligence Platform",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    import uuid
    request_id = str(uuid.uuid4())[:8]
    with structlog.contextvars.bound_contextvars(request_id=request_id):
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


app.include_router(router)
