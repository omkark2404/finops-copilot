from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, Literal, Union
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "finops-copilot"
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"

    database_url_override: Optional[str] = None
    use_local_sqlite: bool = False

    redis_url: str = "redis://localhost:6379/0"
    arq_redis_url: str = "redis://localhost:6379/1"

    data_dir: str = "./data"
    frontend_origin: Optional[str] = None

    duckdb_path: str = "./data/finops-copilot.duckdb"
    parquet_dir: str = "./data/parquet"

    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-3.5-flash-lite"

    jwt_secret_key: str = "secret"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 1440  # 24 hours (prototype default)

    app_env: Literal["development", "production", "test"] = "development"
    log_level: str = "INFO"
    cors_origins: Union[list[str], str] = ["http://localhost:3000"]

    @property
    def cors_origins_list(self) -> list[str]:
        origins = []
        if isinstance(self.cors_origins, list):
            origins = list(self.cors_origins)
        elif isinstance(self.cors_origins, str):
            origins = [
                origin.strip()
                for origin in self.cors_origins.split(",")
                if origin.strip()
            ]
        else:
            origins = ["http://localhost:3000"]

        if self.frontend_origin and self.frontend_origin.strip() not in origins:
            origins.append(self.frontend_origin.strip())

        return origins

    admin_email: str = "admin@finops-copilot.local"
    admin_password: str = "changeme"
    version: str = "0.1.0"

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def database_url(self) -> str:
        """
        Async SQLAlchemy database URL.

        If DATABASE_URL_OVERRIDE is provided, normalize a standard
        PostgreSQL URL to use asyncpg so it can be consumed by
        SQLAlchemy's create_async_engine().
        """
        if self.database_url_override:
            url = self.database_url_override.strip()

            # Supabase and other providers may provide:
            # postgresql://...
            #
            # SQLAlchemy's async engine requires:
            # postgresql+asyncpg://...
            if url.startswith("postgresql://"):
                url = url.replace(
                    "postgresql://",
                    "postgresql+asyncpg://",
                    1,
                )

            return url

        if self.use_local_sqlite or self.postgres_host in (
            "postgres",
            "localhost_sqlite",
            "sqlite",
        ):
            return "sqlite+aiosqlite:///./data/finops-copilot.db"

        return (
            f"postgresql+asyncpg://"
            f"{self.postgres_user}:"
            f"{self.postgres_password}@"
            f"{self.postgres_host}:"
            f"{self.postgres_port}/"
            f"{self.postgres_db}"
        )

    @property
    def sync_database_url(self) -> str:
        """
        Synchronous SQLAlchemy database URL.

        Used only where synchronous PostgreSQL access is required.
        """
        if self.use_local_sqlite or self.postgres_host in (
            "postgres",
            "localhost_sqlite",
            "sqlite",
        ):
            return "sqlite:///./data/finops-copilot.db"

        if self.database_url_override:
            url = self.database_url_override.strip()

            # Normalize asyncpg URL back to standard PostgreSQL
            # before attaching the synchronous psycopg2 driver.
            if url.startswith("postgresql+asyncpg://"):
                url = url.replace(
                    "postgresql+asyncpg://",
                    "postgresql+psycopg2://",
                    1,
                )
            elif url.startswith("postgresql://"):
                url = url.replace(
                    "postgresql://",
                    "postgresql+psycopg2://",
                    1,
                )

            return url

        return (
            f"postgresql+psycopg2://"
            f"{self.postgres_user}:"
            f"{self.postgres_password}@"
            f"{self.postgres_host}:"
            f"{self.postgres_port}/"
            f"{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()