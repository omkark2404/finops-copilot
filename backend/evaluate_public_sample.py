"""Reproduce one fixed, CC BY 4.0 public billing-sample evaluation (not a quality certification)."""

import argparse
import csv
import hashlib
import importlib.metadata
import io
import json
import subprocess
import sys
import tempfile
import urllib.request
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path

COMMIT = "adbdd17a132984d6e8583c149c236d2199c3f5bc"
SOURCE = f"https://raw.githubusercontent.com/FinOps-Open-Cost-and-Usage-Spec/FOCUS-Sample-Data/{COMMIT}/FOCUS-1.0/focus_sample_10000.csv"
SHA256 = "0bf58b73123294c4476b648e647cad842935036f67dc4e9a2cc4a6d7497cc2e3"
LICENSE = (
    f"https://github.com/FinOps-Open-Cost-and-Usage-Spec/FOCUS-Sample-Data/blob/{COMMIT}/license.md"
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", type=Path, help="Optional predownloaded file; checksum is always enforced"
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = (
        args.input.read_bytes() if args.input else urllib.request.urlopen(SOURCE, timeout=30).read()
    )
    if hashlib.sha256(data).hexdigest() != SHA256:
        parser.error("Public source checksum differs from the pinned version")
    source_rows = list(csv.DictReader(io.StringIO(data.decode())))
    expected = sum((Decimal(row["BilledCost"]) for row in source_rows), Decimal(0)).quantize(
        Decimal(".01"), rounding=ROUND_HALF_EVEN
    )
    with tempfile.TemporaryDirectory(prefix="finops-public-eval-") as directory:
        root = Path(directory)
        source = root / "source.csv"
        source.write_bytes(data)
        result = root / "result.json"
        subprocess.run(
            [
                sys.executable,
                str(Path(__file__).with_name("run_evaluation.py")),
                "--input",
                str(source),
                "--sha256",
                SHA256,
                "--source-url",
                SOURCE,
                "--data-license",
                "CC BY 4.0; FOCUS-Sample-Data contributors",
                "--output",
                str(result),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        measured = json.loads(result.read_text())
    actual = Decimal(str(measured["spend"]["total_billed_cost"]))
    if actual != expected:
        raise ValueError(
            "Independent decimal row sum does not reconcile with the API display total"
        )
    output = {
        "source": {
            "publisher": "FinOps-Open-Cost-and-Usage-Spec/FOCUS-Sample-Data contributors",
            "commit": COMMIT,
            "url": SOURCE,
            "sha256": SHA256,
            "license": "CC BY 4.0",
            "license_url": LICENSE,
            "description": "Publisher describes an anonymized real-world sample. This 10,000-row extract is not a complete invoice or representative customer history.",
            "changes": "No source rows removed, filled, reweighted or generated. Aggregate metrics only are redistributed.",
        },
        "environment": {
            "python": measured["python"],
            "packages": {
                name: importlib.metadata.version(name)
                for name in ["pandas", "numpy", "duckdb", "statsmodels", "lightgbm"]
            },
        },
        "rows": len(source_rows),
        "quality": {
            "status": measured["quality"]["overall_status"],
            "issues": measured["quality"]["issues"],
            "warnings": measured["quality"]["warnings"],
        },
        "reconciliation": {
            "currency": measured["spend"]["currency"],
            "independent_decimal_total_at_two_places": str(expected),
            "application_display_total": str(actual),
            "difference": str(actual - expected),
            "rounding": "ROUND_HALF_EVEN, two display decimals",
        },
        "period": {
            "start": measured["spend"]["period_start"],
            "end": measured["spend"]["period_end"],
        },
        "forecast": measured.get("forecast"),
        "forecast_unavailable": measured.get("forecast_unavailable"),
        "anomaly_count": measured["anomaly_count"],
        "limitations": [
            "No anomaly labels: precision/recall cannot be measured.",
            "30 observed days; six-day held-out test is not a 30-day accuracy estimate.",
            "One published sample does not establish customer accuracy or realized savings.",
            "WAPE is an error measure, not an accuracy percentage.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, allow_nan=False) + "\n")
    print(
        "Wrote measured public-sample results; inspect errors and limitations, not a PASS accuracy label"
    )


if __name__ == "__main__":
    main()
