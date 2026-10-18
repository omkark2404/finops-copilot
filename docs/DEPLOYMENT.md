# Deployment runbook

Local Compose is PostgreSQL + one API process + one Next.js process. Database ports are not published; application ports bind to loopback. Named volumes preserve metadata/Parquet. Back up both stores together. Images run as non-root; rebuilding/updating base images is still necessary beyond dependency locks.

The Render blueprint defines one disk-enabled paid-tier backend (Render plan identifier 1c-2g, checked against the current Blueprint reference) with SQLite and Parquet on the same disk. It does not provision Redis or a disconnected worker. Review plan/cost/account settings before using the blueprint. This change does not itself deploy anything. PostgreSQL can instead be supplied with USE_LOCAL_SQLITE=false and DATABASE_URL_OVERRIDE; keep persistent Parquet storage regardless.

Set FRONTEND_ORIGIN to the exact HTTPS frontend origin, COOKIE_SECURE=true and COOKIE_SAMESITE=none for cross-site hosting. Configure NEXT_PUBLIC_API_URL in the frontend's BUILD environment and rebuild after changing it. Never include a secret in NEXT_PUBLIC variables. If browser privacy settings block third-party cookies, serve frontend/API under the same site; do not work around that by storing tokens in localStorage.

Use one API worker. The prototype's compute gate/rate limits are per process, not distributed locks. /live reports process liveness; /health returns 503 when metadata access fails. A configured Gemini key does not prove the external API is available.

Before pointing recruiters at a live URL: sign in, upload a licensed/non-sensitive file, reload, switch datasets, inspect spend, save a run, record review, simulate an explicit assumption and delete. Verify a viewer cannot mutate and another user cannot read the file. Check logs, disk persistence after restart, credential/cookie settings and allowed origins.

Public hosting account ownership, the existing live service configuration and external profile/repository settings are not established by source code changes. No real cloud savings, customer use or uptime promise follows from deployment.

## Repeatable integration checks

`.github/workflows/integration.yml` builds the actual Compose images, checks non-root users, and runs the PostgreSQL-backed login/upload/analytics/forecast/persisted-run/review/scenario/deletion workflow. It also fetches the frontend HTML. A workflow definition is not a passing result; inspect the uploaded `compose-postgresql-results` artifact after it executes on GitHub.

On a Docker-capable local machine, create the private environment and run:

```bash
python3.12 scripts/init_env.py
docker compose up --build --wait --wait-timeout 180
docker compose exec -T backend python verify_integration.py --expected-database postgresql --output /app/data/integration-results.json
```

The checker creates and deletes synthetic fixtures and accepts loopback URLs only. It refuses to label a SQLite connection as PostgreSQL. Its HTTP workflow was exercised locally against SQLite; no Docker engine was available in the preparation environment.

For an actual provider check, configure `GEMINI_API_KEY` as a repository Actions secret and optionally `GEMINI_MODEL` as an Actions variable. Manually run “Deployment and provider verification” with `live_gemini` enabled. The opt-in job makes one small, potentially billable call with fixed non-sensitive aggregates; offline fallback is a failure, not proof of live success. It stores only model/usage/success metadata. Never paste the key into chat or commit it.

The default model was updated to `gemini-3.5-flash-lite` after checking Google's deprecation guidance on 17 October 2026: https://ai.google.dev/gemini-api/docs/deprecations.md . The former 2.5 family is restricted for new users. Listed availability still does not prove this account has access; run the authenticated smoke call.

## Migration 0003: existing duplicates

Before upgrading an existing database, back up metadata and Parquet together. The new owner/content-hash unique index protects simultaneous ingestion. If legacy duplicates exist, startup migration stops with a clear error and preserves all rows.

An administrator can inspect duplicate groups with this read-only SQL:

```sql
SELECT created_by, content_hash, COUNT(*) AS dataset_count
FROM datasets
WHERE created_by IS NOT NULL AND content_hash IS NOT NULL
GROUP BY created_by, content_hash
HAVING COUNT(*) > 1;
```

Review the associated datasets/runs with the owner. Use a previously working application or a reviewed recovery procedure to remove only confirmed duplicates, then retry the migration. Do not blindly delete metadata rows or Parquet folders: related evidence/review records must be handled consistently. No automatic destructive cleanup is included.
