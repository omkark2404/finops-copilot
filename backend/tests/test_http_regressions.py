"""HTTP/security regressions. All generated billing rows are SYNTHETIC TEST FIXTURES."""

import asyncio
import io
from datetime import datetime, timedelta

import pandas as pd
import pytest


@pytest.fixture
def client(tmp_path, monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("USE_LOCAL_SQLITE", "true")
    monkeypatch.setenv("ADMIN_PASSWORD", "local-test-password-123")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    get_settings.cache_clear()
    from app.db import close_db

    asyncio.run(close_db())
    from app.main import app
    from fastapi.testclient import TestClient

    with TestClient(app, headers={"X-FinOps-Client": "1"}) as c:
        yield c
    get_settings.cache_clear()


def login(client, email="admin@test.local"):
    return client.post("/auth/login", json={"email": email, "password": "local-test-password-123"})


def fixture_csv(currency="USD", spike=True):
    start = datetime(2024, 1, 1)
    rows = []
    for day in range(40):
        rows.append(
            {
                "BilledCost": 800 if spike and day == 30 else 100,
                "EffectiveCost": 100,
                "ChargePeriodStart": (start + timedelta(days=day)).isoformat(),
                "ChargePeriodEnd": (start + timedelta(days=day + 1)).isoformat(),
                "BillingCurrency": currency,
                "ServiceName": "Compute",
                "ProviderName": "Example",
                "BillingAccountId": "fixture",
            }
        )
    stream = io.StringIO()
    pd.DataFrame(rows).to_csv(stream, index=False)
    return stream.getvalue().encode()


def upload(client, data=None, name="Fixture"):
    return client.post(
        "/datasets/ingest",
        files={"file": ("fixture.csv", data or fixture_csv(), "text/csv")},
        data={"dataset_name": name},
    )


def test_http_full_journey_and_persistence(client):
    response = login(client)
    assert response.status_code == 200, response.text
    assert "HttpOnly" in response.headers["set-cookie"]
    assert client.get("/auth/me").status_code == 200
    response = upload(client)
    assert response.status_code == 200, response.text
    ident = response.json()["dataset_id"]
    assert isinstance(client.get("/datasets").json(), list)
    assert (
        client.get("/spend/summary", params={"dataset_id": ident}).json()["total_billed_cost"]
        == 4700
    )
    run = client.post("/agent-runs", params={"dataset_id": ident})
    assert run.status_code == 200, run.text
    saved = client.get("/agent-runs", params={"dataset_id": ident}).json()
    assert saved[0]["id"] == run.json()["id"]
    recs = client.get("/recommendations", params={"dataset_id": ident}).json()
    assert recs
    rec = recs[0]["id"]
    sim = client.post(f"/recommendations/{rec}/simulate", json={"reduction_pct": 10})
    assert sim.status_code == 200, sim.text
    assert sim.json()["estimated_savings"] == 470
    assert (
        client.post(f"/recommendations/{rec}/decision", json={"decision": "approved"}).status_code
        == 200
    )
    deleted = client.delete("/datasets/" + ident)
    assert deleted.status_code == 200, deleted.text
    assert client.get("/datasets").json() == []
    assert client.get("/spend/summary", params={"dataset_id": ident}).status_code == 404


def test_permissions_and_csrf(client):
    assert login(client).status_code == 200
    ident = upload(client).json()["dataset_id"]
    for role, email in [
        ("FINOPS_ANALYST", "other@example.com"),
        ("VIEWER", "viewer@example.com"),
    ]:
        assert (
            client.post(
                "/auth/register",
                json={
                    "email": email,
                    "password": "local-test-password-123",
                    "role": role,
                },
            ).status_code
            == 200
        )
    assert login(client, "other@example.com").status_code == 200
    assert client.get("/datasets").json() == []
    assert client.get("/spend/summary", params={"dataset_id": ident}).status_code == 404
    assert client.delete("/datasets/" + ident).status_code == 404
    assert login(client, "viewer@example.com").status_code == 200
    assert upload(client).status_code == 403
    assert client.post("/budgets", json={}).status_code == 403
    assert client.post("/auth/logout", headers={"X-FinOps-Client": ""}).status_code == 403
    assert (
        client.post("/auth/logout", headers={"Origin": "https://untrusted.example"}).status_code
        == 403
    )


def test_upload_validation_dates_limits_and_dedup(client):
    login(client)
    ident = upload(client).json()["dataset_id"]
    assert upload(client).status_code == 409
    assert (
        client.get(
            "/spend/summary",
            params={"dataset_id": ident, "period_start": "2099-01-01' OR TRUE --"},
        ).status_code
        == 422
    )
    assert (
        client.get("/forecasts", params={"dataset_id": ident, "horizon_days": 100000}).status_code
        == 422
    )
    assert (
        client.get(
            "/spend/trend", params={"dataset_id": ident, "period_start": "2099-01-01"}
        ).json()["data_points"]
        == []
    )
    data = fixture_csv().decode().replace("USD", "INR", 1).encode()
    response = upload(client, data)
    assert response.status_code == 400, response.text
    assert len(client.get("/datasets").json()) == 1
    from app.storage import get_uploads_dir

    assert not list(get_uploads_dir().iterdir())


def test_hhi_bounds_and_no_automatic_savings(client):
    login(client)
    ident = upload(client).json()["dataset_id"]
    from app.analytics import get_cost_drivers

    assert get_cost_drivers(ident).concentration_score == 1
    response = client.get("/opportunities", params={"dataset_id": ident})
    assert response.json()["total_potential_savings"] is None


def test_budget_actuals(client):
    login(client)
    upload(client)
    response = client.post(
        "/budgets",
        json={
            "name": "Fixture budget",
            "entity_type": "total",
            "entity_value": "all",
            "period_type": "custom",
            "period_start": "2024-01-01",
            "period_end": "2024-02-09",
            "budget_amount": 5000,
            "currency": "USD",
        },
    )
    assert response.status_code == 200, response.text
    budget = client.get("/budgets").json()[0]
    assert budget["actual_spend"] == 4700
    assert budget["variance"] == -300


def test_causal_anomaly_baseline():
    from app.anomaly import detect_robust_zscore

    series = pd.Series(
        [100.0] * 20 + [900.0] + [100.0] * 20,
        index=pd.date_range("2024-01-01", periods=41),
    )
    before = detect_robust_zscore(series.iloc[:25], "service", "Fixture", "test")
    after = detect_robust_zscore(series, "service", "Fixture", "test")
    assert [(a.detected_at, a.expected_cost) for a in before] == [
        (a.detected_at, a.expected_cost)
        for a in after
        if a.detected_at <= str(series.index[24])[:10]
    ]


def test_forecast_protocol_and_missing_days():
    from app.forecasting import lightgbm_forecast

    series = pd.Series(
        [100.0 + i for i in range(120)], index=pd.date_range("2024-01-01", periods=120)
    )
    result = lightgbm_forecast(series, 7)
    assert "validation_metrics" in result.training_period
    assert result.baseline_metrics is not None
    assert result.training_period["test_start"] > result.training_period["start"]
    assert len(result.points) == 7
    with pytest.raises(ValueError, match="Missing calendar"):
        lightgbm_forecast(series.drop(series.index[5]), 7)


def test_critic_rejects_missing_evidence():
    from app.agents import MockLLMProvider, run_critic_agent
    from app.schemas import OptimizationRecommendation

    rec = OptimizationRecommendation(
        id="rec",
        opportunity_id="opp",
        dataset_id="ds",
        title="Review",
        description="Review",
        actions=[],
        priority_rank=1,
        risk_level="low",
        evidence=[],
        status="pending",
    )
    _, validation, decision = asyncio.run(
        run_critic_agent(
            "run",
            {"data_quality_passed": True, "savings_note": "ESTIMATED"},
            [rec],
            MockLLMProvider(),
        )
    )
    assert not validation.recommendation_safe
    assert decision.decision.value == "REJECT"


def test_password_does_not_silently_truncate():
    from app.auth import hash_password

    with pytest.raises(ValueError, match="72"):
        hash_password("a" * 73)


def test_request_body_limits_before_parsing(client):
    assert (
        client.post(
            "/auth/login", content="x" * 70000, headers={"Content-Type": "application/json"}
        ).status_code
        == 413
    )


def test_lightgbm_candidate_returns_a_valid_result():
    from app.forecasting import _result

    series = pd.Series(
        [100.0 + i % 7 for i in range(90)], index=pd.date_range("2024-01-01", periods=90)
    )
    result = _result(series, 3, "lightgbm", {"mae": 1.0})
    assert result.method.value == "lightgbm"
    assert len(result.points) == 3


def test_numeric_evidence_excludes_identifiers():
    from app.agents import _numeric_evidence

    data = _numeric_evidence(
        {
            "account": "private-account",
            "sensitive-account-as-key": 50,
            "amount": 100,
            "items": [{"id": "secret", "cost": 20}],
        }
    )
    assert data == {"amount": 100, "items": [{"cost": 20}]}


def test_gemini_rejects_ungrounded_output():
    from time import monotonic
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from app.agents import GeminiProvider

    provider = GeminiProvider.__new__(GeminiProvider)
    provider.model = "mock"
    provider.degraded = False
    provider.started = monotonic()
    provider.usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "failures": 0}
    response = SimpleNamespace(text="The total is 987654.", usage_metadata=None)
    provider.client = SimpleNamespace(
        aio=SimpleNamespace(
            models=SimpleNamespace(generate_content=AsyncMock(return_value=response))
        )
    )
    text = asyncio.run(provider.explain({"total": 100}, "Explain total"))
    assert "Offline explanation" in text
    assert provider.degraded and provider.usage["failures"] == 1


def test_existing_metadata_upgrade(client):
    import sqlite3

    from app.config import get_settings
    from app.migrate import upgrade

    path = __import__("pathlib").Path(get_settings().data_dir) / "finops-copilot.db"
    with sqlite3.connect(path) as connection:
        connection.execute("ALTER TABLE pipeline_runs DROP COLUMN payload")
        connection.execute("UPDATE alembic_version SET version_num='0001'")
    upgrade()
    with sqlite3.connect(path) as connection:
        assert "payload" in {
            row[1] for row in connection.execute("PRAGMA table_info(pipeline_runs)")
        }


def test_decimal_reconciliation_and_negative_credits(client):
    assert login(client).status_code == 200
    frame = pd.read_csv(io.BytesIO(fixture_csv(spike=False)))
    frame = frame.iloc[:4].copy()
    frame["BilledCost"] = [0.1, 0.2, -0.1, 0.01]
    frame["EffectiveCost"] = frame["BilledCost"]
    frame["ServiceName"] = ["Compute", "Compute", "Credit", "Storage"]
    result = upload(client, frame.to_csv(index=False).encode(), "Decimal credit fixture")
    assert result.status_code == 200, result.text
    ident = result.json()["dataset_id"]
    summary = client.get("/spend/summary", params={"dataset_id": ident}).json()
    assert summary["total_billed_cost"] == 0.21
    assert summary["service_breakdown"]["Credit"] == -0.1
    assert round(sum(summary["service_breakdown"].values()), 2) == 0.21


def test_net_credit_forecast_is_not_forced_to_zero():
    from app.forecasting import naive_forecast

    series = pd.Series([-100.0] * 12, index=pd.date_range("2024-01-01", periods=12))
    result = naive_forecast(series, 3)
    assert all(point.predicted_cost == -100 for point in result.points)


def test_column_alias_collision_returns_validation_error(client):
    assert login(client).status_code == 200
    frame = pd.read_csv(io.BytesIO(fixture_csv()))
    frame["billed_cost"] = 1
    response = upload(client, frame.to_csv(index=False).encode())
    assert response.status_code == 400, response.text
    assert "conflicting column names" in response.json()["detail"]
    assert client.get("/datasets").json() == []


def test_simultaneous_same_file_has_one_winner(client, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from pathlib import Path

    from app import api
    from app.config import get_settings
    from app.storage import get_uploads_dir

    assert login(client).status_code == 200
    original = api.analysis
    arrivals = 0
    both_ready = asyncio.Event()

    async def force_precheck_race(function, *args, **kwargs):
        nonlocal arrivals
        if function is api.ingest_file:
            arrivals += 1
            if arrivals == 2:
                both_ready.set()
            await asyncio.wait_for(both_ready.wait(), timeout=5)
        return await original(function, *args, **kwargs)

    monkeypatch.setattr(api, "analysis", force_precheck_race)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(upload, client, fixture_csv(), f"Race {i}") for i in range(2)]
        responses = [future.result(timeout=15) for future in futures]
    assert sorted(r.status_code for r in responses) == [200, 409], [r.text for r in responses]
    assert arrivals == 2  # Both really passed the earlier application-level lookup.
    assert len(client.get("/datasets").json()) == 1
    assert len(list((Path(get_settings().data_dir) / "parquet").glob("*/data.parquet"))) == 1
    assert not list(get_uploads_dir().iterdir())


def test_legacy_duplicate_migration_preserves_records_and_requires_review(client):
    import sqlite3
    from pathlib import Path

    from app.config import get_settings
    from app.migrate import upgrade

    assert login(client).status_code == 200
    owner = client.get("/auth/me").json()["id"]
    path = Path(get_settings().data_dir) / "finops-copilot.db"
    with sqlite3.connect(path) as connection:
        connection.execute("DROP INDEX uq_datasets_owner_content_hash")
        connection.executemany(
            "INSERT INTO datasets(id,name,created_by,content_hash,is_demo) VALUES (?,?,?,?,0)",
            [
                ("legacy-one", "legacy duplicate fixture", owner, "a" * 64),
                ("legacy-two", "legacy duplicate fixture", owner, "a" * 64),
            ],
        )
        connection.execute("UPDATE alembic_version SET version_num='0002'")
    with pytest.raises(RuntimeError, match="Duplicate owner/file hashes exist"):
        upgrade()
    with sqlite3.connect(path) as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM datasets WHERE name='legacy duplicate fixture'"
            ).fetchone()[0]
            == 2
        )
        # Explicit owner-reviewed fixture resolution, not automatic production data deletion.
        connection.execute("DELETE FROM datasets WHERE id='legacy-two'")
    upgrade()
    with sqlite3.connect(path) as connection:
        indexes = {row[1] for row in connection.execute("PRAGMA index_list(datasets)")}
        assert "uq_datasets_owner_content_hash" in indexes
        assert (
            connection.execute("SELECT COUNT(*) FROM datasets WHERE id='legacy-one'").fetchone()[0]
            == 1
        )
