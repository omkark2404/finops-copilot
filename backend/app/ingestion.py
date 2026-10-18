"""
FOCUS Billing Data Ingestion Pipeline.

Handles:
- CSV and Parquet file formats
- FOCUS version detection (1.0, 1.0.1)
- Schema validation and data quality checks
- Normalization to canonical cost model
- Content hashing for provenance
- Parquet storage for analytical queries
- Provenance recording

Raw inputs are preserved until successful ingestion, then deleted by the API.
NEVER generates synthetic billing data.
"""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

from .config import get_settings
from .schemas import (
    DataQualityReport,
    FieldQualityMetric,
    FocusVersion,
    QualityStatus,
)
from .time import utcnow

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
    "ConsumedUnit": "consumed_unit",
    "PricingUnit": "pricing_unit",
    "PricingQuantity": "pricing_quantity",
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
    "billed_cost",
    "charge_period_start",
    "charge_period_end",
    "currency",
]

NUMERIC_FIELDS = [
    "billed_cost",
    "effective_cost",
    "list_cost",
    "contracted_cost",
    "quantity",
]
DATE_FIELDS = [
    "charge_period_start",
    "charge_period_end",
    "billing_period_start",
    "billing_period_end",
]


def detect_focus_version(df: pd.DataFrame) -> FocusVersion:
    cols = set(df.columns)
    v1_0_required = {
        "BilledCost",
        "ChargePeriodStart",
        "ChargePeriodEnd",
        "BillingCurrency",
    }
    v1_0_1_cols = {
        "ResourceName",
        "ResourceType",
        "CommitmentDiscountId",
        "PricingUnit",
    }
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


MAX_COLUMNS = 200
MAX_HEADER_CHARS = 65_536
MAX_RECORD_CHARS = 1_000_000


def _validate_columns(names):
    if len(names) > MAX_COLUMNS:
        raise ValueError("At most 200 input columns are supported")
    canonical = [FOCUS_V1_0_1_COLUMNS.get(name, name) for name in names]
    if len(set(canonical)) != len(canonical):
        raise ValueError("Duplicate or conflicting column names after normalization")


def _preflight_csv(path):
    """Bound record size/width before Pandas can allocate arrays or implicit indexes."""
    names = None
    record_chars = 0
    rows = 0
    with path.open(encoding="utf-8-sig", newline="") as stream:

        def lines():
            nonlocal record_chars
            while True:
                limit = MAX_HEADER_CHARS if names is None else MAX_RECORD_CHARS
                line = stream.readline(limit - record_chars + 1)
                if not line:
                    return
                record_chars += len(line)
                if record_chars > limit:
                    raise ValueError("CSV header or record exceeds the supported character limit")
                yield line

        try:
            for row in csv.reader(lines(), strict=True):
                record_chars = 0
                if not row or (len(row) == 1 and not row[0].strip()):
                    continue
                if names is None:
                    names = row
                    _validate_columns(names)
                else:
                    if len(row) != len(names):
                        raise ValueError(
                            "CSV rows must have the same number of fields as the header"
                        )
                    rows += 1
                    if rows > get_settings().max_rows:
                        raise ValueError("Dataset exceeds configured row limit")
        except (csv.Error, UnicodeDecodeError) as error:
            raise ValueError("Invalid UTF-8 CSV or unsupported field size/quoting") from error
    if names is None:
        raise ValueError("CSV must contain a header")


def normalize_to_canonical(df: pd.DataFrame, version: FocusVersion) -> pd.DataFrame:
    """Map provider column names to canonical names. Coerces invalid numeric/date values for explicit validation."""
    _validate_columns(list(df.columns))
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
    now = utcnow()
    issues = []
    warnings = []
    total_rows = len(df)
    if total_rows == 0:
        raise ValueError("Billing dataset must contain rows")
    valid_mask = pd.Series(True, index=df.index)

    # Check for required canonical fields
    missing_required = [f for f in REQUIRED_CANONICAL_FIELDS if f not in df.columns]
    if missing_required:
        issues.append(f"Missing required fields: {missing_required}")
        valid_mask[:] = False

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
                issues.append(f"{col}: {nan_count} missing values ({nan_count / total_rows:.1%})")

        if col in DATE_FIELDS:
            nat_count = int(df[col].isna().sum())
            if nat_count > 0:
                issues.append(f"{col}: {nat_count} invalid or missing dates")

        field_metrics.append(
            FieldQualityMetric(
                field_name=col,
                null_rate=null_rate,
                unique_count=int(df[col].nunique()),
                invalid_count=invalid_count,
                sample_invalids=sample_invalids[:3],
            )
        )

    # Duplicate detection
    id_cols = [
        c
        for c in [
            "charge_period_start",
            "account",
            "service",
            "resource",
            "billed_cost",
        ]
        if c in df.columns
    ]
    duplicate_rows = 0
    if id_cols:
        duplicate_rows = int(df.duplicated(subset=id_cols).sum())
        if duplicate_rows > 0:
            warnings.append(f"{duplicate_rows} potential duplicate rows detected")

    for col in NUMERIC_FIELDS:
        if col in df:
            nonmissing = df[col].dropna()
            if not np.isfinite(nonmissing).all():
                issues.append(f"{col}: nonfinite values")
                valid_mask &= df[col].isna() | np.isfinite(df[col])
    if "billed_cost" in df and (df["billed_cost"].abs() > 1e15).any():
        issues.append("Billed cost exceeds supported numeric range")
        valid_mask &= df["billed_cost"].abs() <= 1e15

    # Currency consistency
    currency_consistent = True
    if "currency" in df.columns:
        currencies = df["currency"].dropna().unique()
        if len(currencies) > 1:
            currency_consistent = False
            issues.append(
                "Mixed billing currencies are not supported; upload one currency per dataset"
            )

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

    for col in REQUIRED_CANONICAL_FIELDS:
        if col in df:
            valid_mask &= df[col].notna()
    if "billed_cost" in df:
        valid_mask &= np.isfinite(df["billed_cost"])
        if not np.isfinite(df["billed_cost"]).all():
            issues.append("Billed costs must be finite")
    if "currency" in df:
        valid_mask &= df["currency"].fillna("").str.fullmatch(r"[A-Z]{3}")
        if not valid_mask.all():
            issues.append("Invalid required row values")
    if all(col in df for col in ["charge_period_start", "charge_period_end"]):
        valid_mask &= df["charge_period_start"] < df["charge_period_end"]
    if not valid_mask.all():
        overall_status = QualityStatus.fail
    valid_rows = int(valid_mask.sum())

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
    if path.exists() and path.stat().st_size > get_settings().max_upload_bytes:
        raise ValueError("Billing file exceeds configured byte limit")
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    if path.suffix.lower() in (".parquet", ".pq"):
        import pyarrow.parquet as pq

        parquet = pq.ParquetFile(file_path)
        metadata = parquet.metadata
        if metadata.num_columns > MAX_COLUMNS:
            raise ValueError("At most 200 input columns are supported")
        _validate_columns(parquet.schema_arrow.names)
        expanded = sum(
            metadata.row_group(i).column(j).total_uncompressed_size
            for i in range(metadata.num_row_groups)
            for j in range(metadata.num_columns)
        )
        if expanded > 128_000_000:
            raise ValueError("Parquet expanded data exceeds 128 MB")
        if metadata.num_rows > get_settings().max_rows:
            raise ValueError("Dataset exceeds configured row limit")
        return pd.read_parquet(file_path)
    elif path.suffix.lower() == ".csv":
        _preflight_csv(path)
        return pd.read_csv(
            file_path, encoding="utf-8-sig", low_memory=False, nrows=get_settings().max_rows + 1
        )
    else:
        raise ValueError(f"Unsupported file format: {path.suffix}. Use CSV or Parquet.")


def compute_provenance(
    df: pd.DataFrame, file_path: str, file_hash: str, source_url: str | None
) -> dict:
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
        "ingestion_timestamp": utcnow().isoformat(),
    }


def ingest_file(
    file_path: str,
    dataset_id: str,
    dataset_name: str,
    source_url: str | None = None,
) -> tuple[dict, DataQualityReport]:
    """
    Full ingestion pipeline.

    Returns:
        (provenance_dict, DataQualityReport)

    Raises:
        FileNotFoundError, ValueError on invalid input.
    Raw inputs are preserved until successful ingestion, then deleted by the API.
    NEVER generates synthetic billing data.
    """
    settings = get_settings()

    # Read raw file
    raw_df = read_focus_file(file_path)
    if len(raw_df.columns) > 200:
        raise ValueError("At most 200 input columns are supported")
    if len(raw_df) > settings.max_rows:
        raise ValueError("Dataset exceeds configured row limit")
    file_hash = compute_file_hash(file_path)

    # Detect FOCUS version
    version = detect_focus_version(raw_df)

    # Normalize to canonical form
    canonical_df = normalize_to_canonical(raw_df, version)

    # Validate
    dq_report = validate_focus_data(canonical_df, version)
    dq_report.dataset_id = dataset_id
    if dq_report.overall_status == QualityStatus.fail:
        raise ValueError("Invalid billing dataset: " + "; ".join(dq_report.issues))
    # Optional dimensions are explicit unknowns; effective cost falls back to billed cost.
    for col in ["provider", "account", "service", "region"]:
        if col not in canonical_df:
            canonical_df[col] = "unknown"
    if "effective_cost" not in canonical_df:
        canonical_df["effective_cost"] = canonical_df["billed_cost"]

    from .storage import (
        get_dataset_parquet_path,
        get_relative_parquet_key,
        verify_dataset_parquet_exists,
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

    # Compute provenance
    provenance = compute_provenance(canonical_df, file_path, file_hash, source_url)
    provenance["focus_version"] = version.value
    provenance["parquet_path"] = relative_key

    return provenance, dq_report
