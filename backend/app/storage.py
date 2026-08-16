"""
Centralized Persistent Storage Module for CloudSpend Intelligence (Prototype Storage).

All runtime analytics files (Parquet datasets, DuckDB database, uploads) resolve
under the root DATA_DIR configuration (env var DATA_DIR).

Local default: ./data
Render Production (Prototype): local filesystem under DATA_DIR

Security:
  - dataset_id is UUID-validated before any path construction to prevent path traversal attacks.
  - PostgreSQL database stores ONLY environment-independent relative keys (parquet/<uuid>/data.parquet).
"""
from __future__ import annotations

import logging
import os
import shutil
import uuid
from pathlib import Path
from typing import Optional, Tuple

from .config import get_settings

logger = logging.getLogger(__name__)


# ── ID Validation ─────────────────────────────────────────────────────────────

def validate_dataset_id(dataset_id: str) -> str:
    """
    Validate that dataset_id is a valid UUID string to prevent path traversal attacks.
    Raises ValueError if invalid.
    """
    try:
        val = uuid.UUID(str(dataset_id))
        return str(val)
    except (ValueError, AttributeError, TypeError):
        raise ValueError(f"Invalid dataset ID format: {dataset_id!r}")


# ── Storage Path Resolvers ────────────────────────────────────────────────────

def get_data_dir() -> Path:
    """Return resolved root DATA_DIR directory (creating if missing)."""
    settings = get_settings()
    data_dir = Path(settings.data_dir).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_parquet_dir() -> Path:
    """Return resolved parquet base directory under DATA_DIR."""
    parquet_dir = get_data_dir() / "parquet"
    parquet_dir.mkdir(parents=True, exist_ok=True)
    return parquet_dir


def get_uploads_dir() -> Path:
    """Return resolved uploads directory under DATA_DIR."""
    uploads_dir = get_data_dir() / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    return uploads_dir


def get_duckdb_path() -> Path:
    """Return resolved DuckDB file path under DATA_DIR."""
    return get_data_dir() / "cloudspend.duckdb"


def get_dataset_dir(dataset_id: str) -> Path:
    """Return resolved directory for a specific dataset."""
    valid_id = validate_dataset_id(dataset_id)
    return get_parquet_dir() / valid_id


def get_dataset_parquet_path(dataset_id: str) -> Path:
    """Return resolved Parquet file path for a specific dataset."""
    return get_dataset_dir(dataset_id) / "data.parquet"


def get_relative_parquet_key(dataset_id: str) -> str:
    """Return environment-independent relative storage key for database storage."""
    valid_id = validate_dataset_id(dataset_id)
    return f"parquet/{valid_id}/data.parquet"


# ── Verification & File Operations ───────────────────────────────────────────

def verify_dataset_parquet_exists(dataset_id: str) -> Tuple[bool, Optional[str]]:
    """
    Verify that the dataset Parquet file exists, is a regular file, and is non-empty.
    Returns (True, None) if valid, or (False, error_reason) if invalid.
    """
    try:
        parquet_path = get_dataset_parquet_path(dataset_id)
        if not parquet_path.exists():
            return False, f"Parquet file missing at {parquet_path}"
        if not parquet_path.is_file():
            return False, f"Path at {parquet_path} is not a regular file"
        if parquet_path.stat().st_size == 0:
            return False, f"Parquet file at {parquet_path} is empty (0 bytes)"
        return True, None
    except Exception as e:
        return False, str(e)


def dataset_parquet_exists(dataset_id: str) -> Tuple[bool, Optional[str]]:
    """Alias for verify_dataset_parquet_exists."""
    return verify_dataset_parquet_exists(dataset_id)


def download_dataset_parquet(dataset_id: str) -> Path:
    """
    Get local Path to dataset Parquet file.
    Raises FileNotFoundError with DATASET_STORAGE_MISSING if missing/empty.
    """
    is_valid, err_msg = verify_dataset_parquet_exists(dataset_id)
    if not is_valid:
        raise FileNotFoundError(
            f"DATASET_STORAGE_MISSING: The dataset metadata exists, but its analytics file is missing. Re-ingestion is required. ({err_msg})"
        )
    return get_dataset_parquet_path(dataset_id)


def delete_dataset_parquet(dataset_id: str) -> None:
    """Permanently delete dataset directory and contents (idempotent)."""
    try:
        dataset_dir = get_dataset_dir(dataset_id)
        if dataset_dir.exists():
            shutil.rmtree(dataset_dir, ignore_errors=True)
            logger.info("Deleted dataset directory: %s", dataset_dir)
    except Exception as e:
        logger.warning("Failed to delete dataset directory for %s: %s", dataset_id, e)


def delete_raw_upload(dataset_id: str) -> None:
    """Delete raw uploaded file if present under uploads/."""
    try:
        valid_id = validate_dataset_id(dataset_id)
        uploads_dir = get_uploads_dir()
        for f in uploads_dir.glob(f"{valid_id}*"):
            f.unlink(missing_ok=True)
    except Exception as e:
        logger.warning("Failed to delete raw upload for %s: %s", dataset_id, e)


def delete_dataset_storage(dataset_id: str) -> None:
    """Delete all local storage files for a dataset (Parquet dir + raw upload)."""
    delete_dataset_parquet(dataset_id)
    delete_raw_upload(dataset_id)
