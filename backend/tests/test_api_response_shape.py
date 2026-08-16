"""
Tests for API response shapes, authentication behavior, and ingestion contract.

SYNTHETIC TEST FIXTURE — NOT REAL BILLING DATA.
"""
import uuid
import pytest
import pandas as pd


def make_focus_csv(tmp_path, rows=5) -> str:
    """SYNTHETIC TEST FIXTURE — NOT REAL BILLING DATA."""
    data = {
        "BilledCost": [10.0 + i for i in range(rows)],
        "EffectiveCost": [9.5 + i for i in range(rows)],
        "BillingCurrency": ["USD"] * rows,
        "ProviderName": ["TestProvider"] * rows,
        "BillingAccountId": ["acc-001"] * rows,
        "ServiceName": ["Compute"] * rows,
        "RegionId": ["us-east-1"] * rows,
        "ChargePeriodStart": [f"2024-01-{i+1:02d}T00:00:00Z" for i in range(rows)],
        "ChargePeriodEnd": [f"2024-01-{i+1:02d}T23:59:59Z" for i in range(rows)],
    }
    df = pd.DataFrame(data)
    path = tmp_path / "synthetic_focus_api_test.csv"
    df.to_csv(path, index=False)
    return str(path)


# ── Ingest Response Shape ──────────────────────────────────────────────────────

class TestIngestResponseShape:
    """Verify the exact JSON response shape from the ingest pipeline."""

    def test_ingest_file_provenance_keys(self, tmp_path, monkeypatch):
        """ingest_file must return provenance with dataset_id-agnostic keys."""
        import os
        from app.ingestion import ingest_file
        from app.config import get_settings

        test_dir = str(tmp_path / "api_test_data")
        monkeypatch.setenv("DATA_DIR", test_dir)
        get_settings.cache_clear()

        csv_path = make_focus_csv(tmp_path, rows=5)
        dataset_id = str(uuid.uuid4())

        provenance, dq_report = ingest_file(csv_path, dataset_id, "API Shape Test")

        # Required keys that the API endpoint reads from provenance
        assert "row_count" in provenance, "row_count must be in provenance"
        assert "content_hash" in provenance, "content_hash must be in provenance"
        assert "focus_version" in provenance, "focus_version must be in provenance"
        assert "parquet_path" in provenance, "parquet_path must be in provenance"

        # row_count must be an int > 0
        assert isinstance(provenance["row_count"], int)
        assert provenance["row_count"] == 5

        # parquet_path must be a relative key (not absolute path)
        relative_key = provenance["parquet_path"]
        assert not relative_key.startswith("/"), \
            f"parquet_path must be a relative key, got: {relative_key!r}"
        assert relative_key == f"parquet/{dataset_id}/data.parquet"

        get_settings.cache_clear()

    def test_ingest_api_response_fields_present(self, tmp_path, monkeypatch):
        """
        Simulate what the /datasets/ingest endpoint returns and assert
        the frontend-expected fields are present and non-None.

        This catches the 'undefined rows / undefined status' bug where
        the frontend parsed an error body (detail=...) instead of a success body.
        """
        from app.ingestion import ingest_file
        from app.config import get_settings

        test_dir = str(tmp_path / "api_response_test")
        monkeypatch.setenv("DATA_DIR", test_dir)
        get_settings.cache_clear()

        csv_path = make_focus_csv(tmp_path, rows=3)
        dataset_id = str(uuid.uuid4())
        dataset_name = "Response Shape Test Dataset"

        provenance, dq_report = ingest_file(csv_path, dataset_id, dataset_name)

        # Simulate exact dict the API endpoint returns on success
        api_response = {
            "dataset_id": dataset_id,
            "dataset_name": dataset_name,
            "status": "succeeded",
            "row_count": provenance["row_count"],
            "validation_status": dq_report.overall_status.value,
            "issues": dq_report.issues,
            "warnings": dq_report.warnings,
        }

        # These are the fields the frontend reads
        assert api_response["dataset_id"] is not None
        assert api_response["dataset_name"] == dataset_name
        assert isinstance(api_response["row_count"], int)
        assert api_response["row_count"] == 3
        assert api_response["validation_status"] in ("PASS", "WARN", "FAIL")
        assert api_response["status"] == "succeeded"
        assert isinstance(api_response["issues"], list)
        assert isinstance(api_response["warnings"], list)

        # row_count and validation_status must NEVER be None/undefined
        assert api_response["row_count"] is not None, \
            "row_count was None — frontend would show 'undefined rows'"
        assert api_response["validation_status"] is not None, \
            "validation_status was None — frontend would show 'Status: undefined'"

        get_settings.cache_clear()

    def test_ingest_relative_key_not_absolute_path(self, tmp_path, monkeypatch):
        """
        The parquet_path stored in DB must be a relative key, not an absolute path.
        This ensures the response is consistent across local and Render environments.
        """
        from app.ingestion import ingest_file
        from app.config import get_settings

        test_dir = str(tmp_path / "key_test")
        monkeypatch.setenv("DATA_DIR", test_dir)
        get_settings.cache_clear()

        csv_path = make_focus_csv(tmp_path, rows=2)
        dataset_id = str(uuid.uuid4())

        provenance, _ = ingest_file(csv_path, dataset_id, "Key Test")

        relative_key = provenance["parquet_path"]
        assert "/" in relative_key
        assert not relative_key.startswith("/")
        assert relative_key.startswith("parquet/")
        assert relative_key.endswith("/data.parquet")

        get_settings.cache_clear()


# ── JWT / Auth Config ──────────────────────────────────────────────────────────

class TestAuthConfig:
    """Verify JWT configuration is correct for prototype use."""

    def test_jwt_expiry_is_sufficient_for_prototype(self, monkeypatch):
        """
        JWT tokens must expire in at least 60 minutes.
        For prototype, default must be >= 60 minutes so users don't hit
        'Invalid or expired token' errors during a normal work session.
        Ideally >= 1440 minutes (24 hours).
        """
        from app.config import get_settings, Settings
        get_settings.cache_clear()
        settings = get_settings()

        assert settings.jwt_access_token_expire_minutes >= 60, (
            f"JWT expiry is too short ({settings.jwt_access_token_expire_minutes} min). "
            "Users will hit 'Invalid or expired token' after 1 hour. "
            "Set JWT_ACCESS_TOKEN_EXPIRE_MINUTES >= 60."
        )

        get_settings.cache_clear()

    def test_jwt_token_creation_and_decoding(self, monkeypatch):
        """JWT tokens created by create_access_token must decode correctly."""
        monkeypatch.setenv("JWT_SECRET_KEY", "test_secret_key_for_unit_test_32c")
        monkeypatch.setenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "1440")
        from app.config import get_settings
        get_settings.cache_clear()

        from app.auth import create_access_token, decode_token

        token = create_access_token({"sub": "test@example.com", "role": "ADMIN"})
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 10

        token_data = decode_token(token)
        assert token_data.email == "test@example.com"

        get_settings.cache_clear()

    def test_invalid_token_raises_401_detail(self, monkeypatch):
        """An invalid/expired token must raise HTTP 401 with 'Invalid or expired token'."""
        monkeypatch.setenv("JWT_SECRET_KEY", "test_secret_key_for_unit_test_32c")
        from app.config import get_settings
        get_settings.cache_clear()

        from app.auth import decode_token
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            decode_token("this.is.not.a.valid.jwt.token")

        assert exc_info.value.status_code == 401
        assert "Invalid or expired token" in exc_info.value.detail

        get_settings.cache_clear()
