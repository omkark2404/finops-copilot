"""Run reproducible offline analysis against a caller-supplied licensed real dataset."""

import argparse
import asyncio
import hashlib
import json
import os
import platform
import tempfile
import time
import uuid
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--data-license", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = args.input.read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    if actual.lower() != args.sha256.lower():
        parser.error("SHA-256 does not match the supplied source checksum")
    with tempfile.TemporaryDirectory(prefix="finops-evaluation-") as directory:
        os.environ["DATA_DIR"] = directory
        # Offline-only evaluation does not need application auth or external API credentials.
        os.environ.setdefault("JWT_SECRET_KEY", "evaluation-only-not-a-server-secret")
        os.environ.setdefault("ADMIN_PASSWORD", "evaluation-only-not-a-server-password")
        from app.config import get_settings

        get_settings.cache_clear()
        from app.agents import MockLLMProvider, run_pipeline
        from app.analytics import get_spend_summary
        from app.anomaly import run_anomaly_detection
        from app.forecasting import forecast_total_spend
        from app.ingestion import ingest_file

        ident = str(uuid.uuid4())
        started = time.perf_counter()
        provenance, quality = ingest_file(
            str(args.input), ident, "Licensed evaluation", args.source_url
        )
        elapsed = time.perf_counter() - started
        output = {
            "python": platform.python_version(),
            "source": args.source_url,
            "data_license": args.data_license,
            "sha256": actual,
            "provenance": provenance,
            "quality": quality.model_dump(mode="json"),
            "ingestion_seconds": elapsed,
            "spend": get_spend_summary(ident).model_dump(mode="json"),
            "anomaly_count": run_anomaly_detection(ident).total_anomalies,
            "methodology": "Execution measurements; no accuracy/savings PASS label",
        }
        try:
            output["forecast"] = forecast_total_spend(ident).model_dump(mode="json")
        except ValueError as error:
            output["forecast_unavailable"] = str(error)
        output["pipeline"] = asyncio.run(run_pipeline(ident, MockLLMProvider())).model_dump(
            mode="json"
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(output, indent=2, default=str, allow_nan=False) + "\n")
        print("Wrote measured results to", args.output)


if __name__ == "__main__":
    main()
