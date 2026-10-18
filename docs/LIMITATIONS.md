# Boundaries

- Portfolio prototype; no production-grade, zero-downtime, zero-hallucination or verified-savings guarantee.
- Per-owner authorization plus admin access, not a certified enterprise tenancy model. Account provisioning is administrator-only.
- One process, local Parquet and bounded serialized compute; no distributed queue, multi-node analytical engine or object storage.
- Bill ingestion does not provide utilization telemetry, tagging allocation, commitment economics, unit economics or automated rightsizing.
- Investigations are not confirmed waste. No automatic savings total is produced. Whole-dataset user scenarios are hypothetical and overlap.
- Generated explanations can be wrong even after numeric checking. No empirical calibration of heuristic scores is claimed.
- Fixed-origin test windows can be shorter than future forecast horizons. Missing days are rejected. No calibrated prediction intervals or labeled anomaly precision/recall study.
- Free/ephemeral hosts lose Parquet unless a persistent volume is configured. PostgreSQL alone does not preserve analytical files.
- Request limits are per process and IP, intended for a single-instance prototype. Add edge/distributed limits before scaling.
- Deletion spans SQL metadata and filesystem operations, without a cross-storage transaction; back up both together and monitor/retry failures.
- Money uses decimal SQL aggregation but floating-point API/scenario displays. This is not an accounting ledger.
- Upstream source/license rights, profile metadata, hosting-account ownership and live deployment need maintainer verification; see PROVENANCE and REMEDIATION.

Next steps should follow measured workloads and licensed representative evaluation, rather than speculative billion-row claims or fine-tuning guarantees.
