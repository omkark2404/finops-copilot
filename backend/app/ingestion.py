"""
FOCUS Billing Data Ingestion Pipeline.

Handles:
- CSV and Parquet file formats
- FOCUS version detection (1.0, 1.0.1)
- Schema validation and data quality checks
- Normalization to canonical cost model
- Content hashing for deduplication
- Parquet storage for analytical queries
- Provenance recording

NEVER silently mutates raw data.
NEVER generates synthetic billing data.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import duckdb
import numpy as np
import pandas as pd

from .config import get_settings
from .schemas import (
    DataQualityReport, DatasetInfo, FieldQualityMetric, FocusVersion, QualityStatus
)

# FOCUS canonical column mappings by version
# Maps provider-specific names to canonical names
FOCUS_V1_0_COLUMNS = {
    "BilledCost": "billed_cost",
    "EffectiveCost": "effective_cost",
    "ListCost": "list_cost",
    "ContractedCost": "contracted_cost",
    "ConsumedQuantity": "quantity",
    "ProviderName": "provider",
    "BillingAccountId": "account",
    "SubAccountId": "sub_account",
    "ServiceName": "service",
    "ServiceCategory": "category",
    "ResourceId": "resource",
    "RegionId": "region",
    "SkuId": "sku",
    "ChargeCategory": "charge_category",
    "PricingCategory": "pricing_category",
    "ChargePeriodStart": "charge_period_start",
    "ChargePeriodEnd": "charge_period_end",
    "BillingPeriodStart": "billing_period_start",
    "BillingPeriodEnd": "billing_period_end",
    "BillingCurrency": "currency",
}

FOCUS_V1_0_1_COLUMNS = {
    **FOCUS_V1_0_COLUMNS,
    # 1.0.1 additions/renames
    "ConsumedUnit": "consumed_unit",
    "PricingUnit": "pricing_unit",
    "PricingQuantity": "pricing_quantity",
    "ResourceName": "resource_name",
    "ResourceType": "resource_type",
    "CommitmentDiscountId": "commitment_discount_id",
    "CommitmentDiscountType": "commitment_discount_type",
    "CommitmentDiscountCategory": "commitment_discount_category",
}

REQUIRED_CANONICAL_FIELDS = [
    "billed_cost", "charge_period_start", "charge_period_end", "currency"
]

NUMERIC_FIELDS = ["billed_cost", "effective_cost", "list_cost", "contracted_cost", "quantity"]
DATE_FIELDS = ["charge_period_start", "charge_period_end", "billing_period_start", "billing_period_end"]


def detect_focus_version(df: pd.DataFrame) -> FocusVersion:
    cols = set(df.columns)
    v1_0_required = {"BilledCost", "ChargePeriodStart", "ChargePeriodEnd", "BillingCurrency"}
    v1_0_1_cols = {"ResourceName", "ResourceType", "CommitmentDiscountId", "PricingUnit"}
    if v1_0_1_cols.intersection(cols):
        return FocusVersion.v1_0_1
    if v1_0_required.issubset(cols):
        return FocusVersion.v1_0
    # Check if columns are already in canonical form
    canonical = {"billed_cost", "charge_period_start", "charge_period_end", "currency"}
    if canonical.issubset(cols):
        return FocusVersion.v1_0
    return FocusVersion.unknown


def get_column_mapping(version: FocusVersion) -> dict[str, str]:
    if version == FocusVersion.v1_0_1:
        return FOCUS_V1_0_1_COLUMNS
    return FOCUS_V1_0_COLUMNS


def normalize_to_canonical(df: pd.DataFrame, version: FocusVersion) -> pd.DataFrame:
    """Map provider column names to canonical names. Does not modify values."""
    mapping = get_column_mapping(version)
    # Only rename columns that exist in the dataframe
    rename_map = {k: v for k, v in mapping.items() if k in df.columns}
    canonical_df = df.rename(columns=rename_map)

    # Parse date columns
    for col in DATE_FIELDS:
        if col in canonical_df.columns:
            canonical_df[col] = pd.to_datetime(canonical_df[col], utc=True, errors="coerce")

    # Ensure numeric fields are float
    for col in NUMERIC_FIELDS:
        if col in canonical_df.columns:
            canonical_df[col] = pd.to_numeric(canonical_df[col], errors="coerce")

    return canonical_df


def compute_file_hash(file_path: str) -> str:
    """SHA-256 hash of raw file for provenance."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_focus_data(df: pd.DataFrame, version: FocusVersion) -> DataQualityReport:
    """Comprehensive data quality validation."""
    now = datetime.utcnow()
    issues = []
    warnings = []
    total_rows = len(df)

    # Check for required canonical fields
    missing_required = [f for f in REQUIRED_CANONICAL_FIELDS if f not in df.columns]
    if missing_required:
        issues.append(f"Missing required fields: {missing_required}")

    # Null rate per field
    null_rate_by_field = {}
    field_metrics = []
    for col in df.columns:
        null_rate = df[col].isna().mean()
        null_rate_by_field[col] = round(float(null_rate), 4)
        invalid_count = 0
        sample_invalids = []

        if col in NUMERIC_FIELDS:
            invalid_mask = df[col] < 0
            # Note: negative costs can be legitimate (credits), warn rather than error
            invalid_count = int(invalid_mask.sum())
            if invalid_count > 0:
                warnings.append(f"{col}: {invalid_count} negative values (may be credits)")
            nan_count = int(df[col].isna().sum())
            if nan_count > total_rows * 0.1:
                issues.append(f"{col}: {nan_count} missing values ({nan_count/total_rows:.1%})")

        if col in DATE_FIELDS:
            nat_count = int(df[col].isna().sum())
            if nat_count > 0:
                issues.append(f"{col}: {nat_count} invalid or missing dates")

        field_metrics.append(FieldQualityMetric(
            field_name=col,
            null_rate=null_rate,
            unique_count=int(df[col].nunique()),
            invalid_count=invalid_count,
            sample_invalids=sample_invalids[:3],
        ))

    # Duplicate detection
    id_cols = [c for c in ["charge_period_start", "account", "service", "resource", "billed_cost"] if c in df.columns]
    duplicate_rows = 0
    if id_cols:
        duplicate_rows = int(df.duplicated(subset=id_cols).sum())
        if duplicate_rows > 0:
            warnings.append(f"{duplicate_rows} potential duplicate rows detected")

    # Currency consistency
    currency_consistent = True
    if "currency" in df.columns:
        currencies = df["currency"].dropna().unique()
        if len(currencies) > 1:
            currency_consistent = False
            warnings.append(f"Multiple currencies detected: {list(currencies)}")

    # Date range validation
    date_range_valid = True
    if "charge_period_start" in df.columns and "charge_period_end" in df.columns:
        bad_dates = df[df["charge_period_start"] > df["charge_period_end"]]
        if len(bad_dates) > 0:
            date_range_valid = False
            issues.append(f"{len(bad_dates)} rows have charge_period_start > charge_period_end")

    # Invalid cost values (NaN billed_cost)
    if "billed_cost" in df.columns:
        nan_costs = int(df["billed_cost"].isna().sum())
        if nan_costs > 0:
            issues.append(f"{nan_costs} rows have missing billed_cost")

    # Overall status
    if issues:
        overall_status = QualityStatus.fail
    elif warnings:
        overall_status = QualityStatus.warn
    else:
        overall_status = QualityStatus.pass_

    valid_rows = total_rows - duplicate_rows

    return DataQualityReport(
        dataset_id="",  # Filled in after dataset creation
        overall_status=overall_status,
        total_rows=total_rows,
        valid_rows=valid_rows,
        duplicate_rows=duplicate_rows,
        null_rate_by_field=null_rate_by_field,
        field_metrics=field_metrics,
        currency_consistency=currency_consistent,
        date_range_valid=date_range_valid,
        issues=issues,
        warnings=warnings,
        generated_at=now,
    )


def read_focus_file(file_path: str) -> pd.DataFrame:
    """Read CSV or Parquet FOCUS file."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    if path.suffix.lower() in (".parquet", ".pq"):
        return pd.read_parquet(file_path)
    elif path.suffix.lower() == ".csv":
        return pd.read_csv(file_path, low_memory=False)
    else:
        raise ValueError(f"Unsupported file format: {path.suffix}. Use CSV or Parquet.")


def compute_provenance(df: pd.DataFrame, file_path: str, file_hash: str, source_url: Optional[str]) -> dict:
    """Record full data provenance."""
    start = end = None
    for col in ["charge_period_start", "billing_period_start"]:
        if col in df.columns and not df[col].isna().all():
            start = str(df[col].min())
            end = str(df[col].max())
            break

    currency = None
    if "currency" in df.columns:
        currencies = df["currency"].dropna().unique()
        currency = str(currencies[0]) if len(currencies) == 1 else ",".join(map(str, currencies))

    return {
        "source_url": source_url,
        "file_path": file_path,
        "content_hash": file_hash,
        "row_count": len(df),
        "date_range_start": start,
        "date_range_end": end,
        "currency": currency,
        "ingestion_timestamp": datetime.utcnow().isoformat(),
    }


def ingest_file(
    file_path: str,
    dataset_id: str,
    dataset_name: str,
    source_url: Optional[str] = None,
) -> tuple[dict, DataQualityReport]:
    """
    Full ingestion pipeline.

    Returns:
        (provenance_dict, DataQualityReport)

    Raises:
        FileNotFoundError, ValueError on invalid input.
    NEVER silently mutates raw data.
    NEVER generates synthetic billing data.
    """
    settings = get_settings()

    # Read raw file
    raw_df = read_focus_file(file_path)
    file_hash = compute_file_hash(file_path)

    # Detect FOCUS version
    version = detect_focus_version(raw_df)

    # Normalize to canonical form
    canonical_df = normalize_to_canonical(raw_df, version)

    # Validate
    dq_report = validate_focus_data(canonical_df, version)
    dq_report.dataset_id = dataset_id

    from .storage import (
        get_dataset_parquet_path,
        get_relative_parquet_key,
        verify_dataset_parquet_exists,
        get_duckdb_path,
    )

    # Write canonical Parquet under DATA_DIR/parquet/<dataset_id>/data.parquet
    parquet_path = get_dataset_parquet_path(dataset_id)
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    canonical_df.to_parquet(parquet_path, index=False, engine="pyarrow")

    # Immediate post-write verification
    is_valid, err_msg = verify_dataset_parquet_exists(dataset_id)
    if not is_valid:
        raise RuntimeError(f"Parquet verification failed after write: {err_msg}")

    # Relative key stored in DB record (environment-independent)
    relative_key = get_relative_parquet_key(dataset_id)

    # Register in DuckDB
    duck = get_duck_for_ingestion(settings)
    table_name = f"dataset_{dataset_id.replace('-', '_')}"
    duck.execute(f"""
        CREATE OR REPLACE TABLE {table_name} AS
        SELECT * FROM read_parquet('{parquet_path}')
    """)

    # Compute provenance
    provenance = compute_provenance(canonical_df, file_path, file_hash, source_url)
    provenance["focus_version"] = version.value
    provenance["parquet_path"] = relative_key
    provenance["duckdb_table"] = table_name

    return provenance, dq_report


def get_duck_for_ingestion(settings):
    """Get DuckDB connection for ingestion."""
    from .storage import get_duckdb_path
    from .db import get_duck
    try:
        return get_duck()
    except Exception:
        import duckdb
        duck_path = get_duckdb_path()
        duck_path.parent.mkdir(parents=True, exist_ok=True)
        return duckdb.connect(str(duck_path))
