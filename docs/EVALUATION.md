# Reproducible evaluation

Previous README numbers are withdrawn as unverified for this checkout. No retained count or benchmark is evidence of real predictive quality.

Supply a licensed real CSV/Parquet with complete daily coverage for forecasts:

```bash
cd backend
.venv/bin/python run_evaluation.py --input /absolute/path/billing.csv \
  --sha256 <verified-source-checksum> --source-url <documented-source> \
  --data-license <license-or-permission-reference> --output /tmp/finops-evaluation.json
```

The runner verifies the hash, uses a valid UUID and temporary storage, records environment/source/row/period information, and returns measured ingestion duration, spend, anomaly count and recursive forecast/test/baseline metrics when the data supports them. It uses offline explanations. It does not declare arbitrary metrics PASS or claim that sample data is authentic customer billing.

A completed run proves execution only. Assess forecast errors against business tolerances and matched baselines; assess anomaly usefulness with labeled/reviewed alerts, false positives and missed events. The public-sample result below is now reproducible. Labeled anomaly precision/recall, realized savings and customer user counts remain unestablished.

Synthetic tests and browser screenshots are engineering verification, clearly separate from this real-data evaluation. CI runs tests, typecheck, lint, build and a browser workflow; test counts belong in actual run output rather than a static accuracy badge.

## Pinned public-data run

See [aggregate results](evaluation/public-focus-10000.json). The FOCUS-Sample-Data contributors describe the source as anonymized real-world billing data and publish it under CC BY 4.0. Attribution, immutable source URL, repository commit and SHA-256 are included in the result. No source rows were deleted, generated or reweighted; the 10,000-line sample is not a complete customer invoice.

```bash
# From the repository root; downloads and verifies the pinned public source.
backend/.venv/bin/python backend/evaluate_public_sample.py --output /tmp/public-focus-results.json
```

Observed 17 October 2026: 10,000 rows, USD, 1–30 September 2024. Independent decimal summation and the application's two-decimal billed-cost display both return **151.43**, difference **0.00**. Quality is WARN: negative credit-like values and 49 potential duplicate rows are disclosed and retained.

The selected moving-average model has **test WAPE 0.801 (80.1% error)**, MAE 10.8703 and RMSE 17.3519. Naive test MAE is also 10.8703. This does not establish useful predictive accuracy or a meaningful improvement over the baseline. Selection uses six validation days and evaluation uses six later test days; neither is evidence of 30-day predictive performance. LightGBM is correctly ineligible because the training sample is too short.

There are 100 statistical flags, but no trusted anomaly labels. That is a count, not precision/recall or evidence of confirmed waste. Obtain longer representative billing histories and reviewed labels before claiming predictive quality. Do not tune hyperparameters against this held-out test and then present it as untouched evaluation.
