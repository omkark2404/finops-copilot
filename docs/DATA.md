# Data contract and financial semantics

The parser accepts a **FOCUS-inspired subset**, not certified full FOCUS conformance. Specification: https://focus.finops.org/ and https://github.com/FinOps-Open-Cost-and-Usage-Spec/FOCUS_Spec . Column-based version hints are not conformance certificates.

Required source columns: BilledCost, ChargePeriodStart, ChargePeriodEnd and BillingCurrency (or canonical snake_case equivalents). Dates are parsed as UTC, required costs must be finite, end timestamps must follow starts, and currency must be one uppercase three-letter code per file. Mixed currencies are rejected; FX conversion is not implemented.

Optional EffectiveCost falls back to billed cost where absent; optional provider/account/service/region dimensions become unknown. Additional mappings include account, resource, SKU, units and commitment fields, but no utilization/commitment-purchase conclusion is derived from their presence.

Invalid required rows reject the upload before Parquet storage. Potential duplicate billing rows are reported, not silently dropped, because apparently identical charges can be legitimate. Valid rows count rows passing required checks, not total minus guessed duplicates. Same raw file hash per owner returns 409; delete the earlier record for intentional re-ingestion.

Limits: 20 MB upload default, 100,000 rows, 200 columns; Parquet expanded metadata is bounded at 128 MB. More than 1000 anomaly entities is rejected explicitly. Breakdown endpoints cap display rows; shares use full net spend, not only visible rows.

SQL binds data values and allowlists grouping identifiers. Costs aggregate as DECIMAL(28,8) and display at two decimals; JSON and metadata scenario values are finite floating-point displays, not a general-ledger decimal API. Credits remain negative costs. HHI uses all positive gross service spend in a mutually exclusive service partition; credit lines are excluded from HHI's denominator.

Calendar end dates include the entire UTC day using a half-open next-day bound. Period changes compare the selected window with an equal-length immediately preceding window and require earlier coverage. This is not necessarily month-over-month.

Raw uploads are deleted after ingestion, including errors. Canonical Parquet remains under DATA_DIR/parquet/<uuid>/data.parquet; related metadata and files are removed on authorized deletion. Source URL is recorded for provenance, never fetched by the API. Billing identifiers must not be committed.

Synthetic fixtures are allowed for engineering tests, browser screenshots and demonstration only, explicitly labeled SYNTHETIC TEST FIXTURE. They do not establish real-world accuracy, customer use or savings. Real-data evaluations require a source, checksum and license/permission.

## Schema preflight and concurrent uploads

CSV schemas are inspected before Pandas loads arrays. Headers are limited to 65,536 characters, each data record to 1,000,000 characters, and the file to the configured row/byte limits. UTF-8 BOMs, quoted commas and quoted newlines are supported. Nonblank records must match the header width; unsupported field size/quoting is rejected. Parquet column count and canonical names are checked from metadata before loading data.

Raw duplicate headers and distinct names mapping to the same canonical field (for example BilledCost plus billed_cost) are rejected with a validation error. The application does not choose one value silently.

A unique database index on `(created_by, content_hash)` makes same-owner raw-file deduplication atomic, including simultaneous requests. The losing request receives 409 and its temporary upload/Parquet files are cleaned up. Different owners can independently ingest the same file. Legacy rows with unknown owner/hash cannot be deduplicated safely from those missing values.

Migration 0003 refuses existing non-null owner/hash duplicates without deleting records. Back up metadata and Parquet, review duplicates and resolve only confirmed duplicates before retrying. See DEPLOYMENT.md.
