"""Exercise disposable local deployments; never point this mutating check at production."""

import argparse
import json
import os
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

import httpx
from dotenv import dotenv_values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--frontend-url")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--expected-database", choices=["sqlite", "postgresql"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    for url in [args.api_url, args.frontend_url]:
        if url and urlparse(url).hostname not in {"localhost", "127.0.0.1", "::1"}:
            parser.error(
                "This check creates/deletes fixtures and supports loopback deployments only"
            )
    config = {**(dotenv_values(args.env_file) if args.env_file else {}), **os.environ}
    email = config.get("ADMIN_EMAIL", "admin@finops-copilot.local")
    password = config.get("ADMIN_PASSWORD")
    if not password:
        parser.error("Configure the disposable deployment admin credentials; never print them")
    checks = {}
    with httpx.Client(
        base_url=args.api_url, timeout=90, trust_env=False, headers={"X-FinOps-Client": "1"}
    ) as client:
        deadline = time.monotonic() + 30
        while True:
            try:
                response = client.get("/health")
                response.raise_for_status()
                break
            except httpx.HTTPError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.5)
        health = response.json()
        assert health["database_backend"] == args.expected_database, health
        checks["database_backend"] = health["database_backend"]
        client.post("/auth/login", json={"email": email, "password": password}).raise_for_status()
        assert client.get("/auth/me").status_code == 200
        checks["session"] = "passed"
        rows = [
            "BilledCost,EffectiveCost,ChargePeriodStart,ChargePeriodEnd,BillingCurrency,ServiceName,ProviderName"
        ]
        for day in range(40):
            start = datetime(2024, 1, 1, tzinfo=UTC) + timedelta(days=day)
            end = start + timedelta(days=1)
            rows.append(
                f"{800 if day == 30 else 100},100,{start.isoformat()},{end.isoformat()},USD,Compute,SyntheticFixture"
            )
        upload = client.post(
            "/datasets/ingest",
            data={"dataset_name": "SYNTHETIC INTEGRATION FIXTURE"},
            files={"file": ("fixture.csv", "\n".join(rows).encode(), "text/csv")},
        )
        upload.raise_for_status()
        ident = upload.json()["dataset_id"]
        try:
            params = {"dataset_id": ident}
            summary = client.get("/spend/summary", params=params)
            summary.raise_for_status()
            assert summary.json()["total_billed_cost"] == 4700
            forecast = client.get("/forecasts", params={**params, "horizon_days": 7})
            forecast.raise_for_status()
            assert len(forecast.json()["points"]) == 7
            run = client.post("/agent-runs", params=params)
            run.raise_for_status()
            saved = client.get("/agent-runs", params=params)
            saved.raise_for_status()
            assert saved.json()[0]["id"] == run.json()["id"]
            recommendations = client.get("/recommendations", params=params)
            recommendations.raise_for_status()
            rec = recommendations.json()[0]["id"]
            client.post(
                f"/recommendations/{rec}/decision", json={"decision": "approved"}
            ).raise_for_status()
            scenario = client.post(f"/recommendations/{rec}/simulate", json={"reduction_pct": 10})
            scenario.raise_for_status()
            assert scenario.json()["estimated_savings"] == 470
            checks["upload_spend_forecast_saved_run_review_scenario"] = "passed"
        finally:
            client.delete("/datasets/" + ident).raise_for_status()
        assert client.get("/datasets/" + ident).status_code == 404
        checks["delete"] = "passed"
    if args.frontend_url:
        page = httpx.get(args.frontend_url.rstrip("/") + "/login", timeout=30, trust_env=False)
        page.raise_for_status()
        assert "FinOps Copilot" in page.text
        checks["frontend_html"] = "passed (not a browser interaction test)"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps({"checks": checks, "synthetic_fixture": True}, indent=2) + "\n"
    )
    print("Integration checks passed; wrote non-secret results to", args.output)


if __name__ == "__main__":
    main()
