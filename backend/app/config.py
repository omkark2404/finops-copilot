"""Validated runtime settings."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "finopscopilot"
    postgres_user: str = "finopsuser"
    postgres_password: str = ""
    database_url_override: str | None = None
    use_local_sqlite: bool = True
    data_dir: str = "./data"
    frontend_origin: str | None = None
    cors_origins: str = "http://localhost:3000"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.5-flash-lite"
    llm_timeout_seconds: float = Field(default=15, gt=0, le=60)
    llm_run_timeout_seconds: float = Field(default=30, gt=0, le=60)
    llm_max_calls: int = Field(default=8, ge=0, le=20)
    jwt_secret_key: str = Field(min_length=24)
    jwt_algorithm: Literal["HS256"] = "HS256"
    jwt_access_token_expire_minutes: int = Field(default=60, ge=5, le=1440)
    admin_email: str = "admin@finops-copilot.local"
    admin_password: str = Field(min_length=12)
    cookie_secure: bool = False
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    app_env: Literal["development", "production", "test"] = "development"
    log_level: str = "INFO"
    max_upload_bytes: int = Field(default=20_000_000, gt=0, le=100_000_000)
    max_rows: int = Field(default=100_000, gt=0, le=1_000_000)
    version: str = "0.2.0"
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    @property
    def cors_origins_list(self):
        return list(
            dict.fromkeys(
                x.strip()
                for x in (self.cors_origins + "," + (self.frontend_origin or "")).split(",")
                if x.strip()
            )
        )

    @property
    def database_url(self):
        if self.database_url_override:
            return self.database_url_override.replace("postgresql://", "postgresql+asyncpg://", 1)
        if self.use_local_sqlite:
            return "sqlite+aiosqlite:///" + str(Path(self.data_dir).resolve() / "finops-copilot.db")
        return URL.create(
            "postgresql+asyncpg",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        ).render_as_string(hide_password=False)

    @model_validator(mode="after")
    def production_secrets(self):
        if self.app_env == "production":
            if not self.cookie_secure or len(self.jwt_secret_key) < 32:
                raise ValueError(
                    "Production requires secure cookies and a 32+ character JWT secret"
                )
            if (
                "changeme" in self.admin_password.lower()
                or "changeme" in self.jwt_secret_key.lower()
            ):
                raise ValueError("Replace placeholder production secrets")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
