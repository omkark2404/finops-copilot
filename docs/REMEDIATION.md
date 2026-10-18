# Audit remediation ledger

Prepared 17 October 2026 against main `a6fdbeb`. Numbers map to the 70 findings in the preceding audit. “Changed” describes source changes; runtime verification and external obligations are separate below. Scope corrections remove unsupported promises rather than inventing enterprise features.

| Audit items | Resolution | Evidence |
| --- | --- | --- |
| 1 | Changed clone URL and directory to the maintained repository. | README |
| 2–6 | Preserved history; documented duplicate trees, placeholder author metadata and uncertain origin. Owner must supply factual provenance and a verified future commit email. | PROVENANCE.md |
| 7–11 | Unified FC/FinOps Copilot branding, browser/social metadata, icon, package repository URL and dataset storage key. | frontend/src/app/layout.tsx, icon.svg, components/Layout.tsx, lib/useDataset.ts, package.json |
| 12–13 | External: profile bio/pins and repository description/topics require GitHub account access. Suggested truthful text below. | GitHub settings |
| 14–15 | Removed production, zero-hallucination and unsubstantiated benchmark claims. Runner requires checksum, source and data license; real-data accuracy remains unverified. | README, EVALUATION.md, backend/run_evaluation.py |
| 16–19 | Removed build bypasses, fixed frontend types and API contracts; unsupported investigation mutation removed. | frontend/next.config.mjs, lib/api.ts, lib/types.ts, backend/app/api.py |
| 20–21 | HTTP-only sessions, logout/expiry handling and same-tab dataset synchronization. | backend/app/auth.py, main.py, frontend/lib/api.ts, useDataset.ts |
| 22–24 | Real deletion, saved full workflow payloads, persisted review/scenario endpoints and mutation audit records. Approval records a human decision; it does not operate cloud infrastructure. | backend/app/api.py, migrations/versions/0002_pipeline_payload.py |
| 25 | User-selected budget dates/currency and observed spend/variance. Multiple matching datasets return unavailable to avoid double counting. | backend/app/api.py, frontend/src/app/budgets/page.tsx |
| 26–28 | Bound SQL, date/dimension validation, per-owner authorization, role gates, upload/body/row/model bounds and per-process request rates. | backend/app/query.py, api.py, body_limit.py, main.py |
| 29–32 | Reject mixed currencies; currency-aware display; service-only HHI; populated driver growth; consistent inclusive calendar windows and adjacent-period comparison. | ingestion.py, analytics.py, frontend/src/lib/format.ts |
| 33–34 | Reject failed required-row checks; valid-row semantics; row/column/expanded-Parquet limits; owner hash deduplication; one Parquet analytical store. Validator explicitly covers a FOCUS subset. | ingestion.py, api.py, DATA.md |
| 35–36 | Removed mixed-unit waste inference, arbitrary savings percentages and summed overlapping savings. Opportunities require investigation. Scenarios use explicit user assumptions and whole observed spend. | optimization.py, agents.py, api.py |
| 37–39 | Fixed forecast schema; comparable candidate selection; recursive validation/test; common feature calculation; full-history final refit; missing-day rejection. No empirical predictive-quality claim. | forecasting.py, schemas.py, ML.md |
| 40 | Prior-only anomaly baselines; deterministic bounded entity coverage; no silent first-50/first-100 truncation. Scores remain heuristics. | anomaly.py |
| 41–45 | Numeric/bool-only redacted external evidence; grounding checks; missing/contradictory evidence rejects review; full payloads; explicit offline/degraded output, call/token/time budgets and usage records. Monetary API cost needs provider reconciliation. Seven sequential stages are described honestly. | agents.py, AGENTS.md |
| 46–49 | Explicit SQLite/PostgreSQL selection, complete locked Python dependencies, migrations, consistent root environment setup and private generated credentials. | config.py, requirements*.txt, scripts/init_env.py, start-local.sh, README |
| 50–51 | Removed disconnected worker/Redis claims. Bounded serialized thread execution and thread-local in-memory DuckDB. No distributed queue claim. | execution.py, db.py, ARCHITECTURE.md |
| 52–55 | Build-time frontend URL, durable-volume configuration, origin/cookie guidance, common data root, readiness/liveness, redacted errors, migrations and non-root containers. Docker/hosted runtime still needs verification. | DEPLOYMENT.md, render.yaml, Dockerfiles, .dockerignore files, docker-compose.yml |
| 56–57 | Maintained dependency updates/locks, CI/audits, bounded auth inputs and bcrypt byte-length rejection. | requirements*.txt, package-lock.json, .github, auth.py, schemas.py |
| 58 | Decimal SQL aggregation and explicit currency/credit semantics. API/scenario/model values remain floating point; this prototype is not an accounting ledger. | analytics.py, DATA.md, LIMITATIONS.md |
| 59 | Added real HTTP boundary, isolation, deletion, persistence, malicious input, model, causal-prefix, migration and browser workflow regressions. | backend/tests/test_http_regressions.py, frontend/tests/workflow.spec.ts |
| 60–62 | Missing values display unavailable, correct forecast horizon/share denominator, local error states and stale-request guards. Independent screens can recompute analysis; cross-request caching is not implemented. | frontend/src/components/MetricCard.tsx, lib/format.ts, app pages |
| 63–65 | Responsive grids/navigation/tables, keyboard controls, associated labels, inline deletion confirmation, focus and reduced-motion rules; removed hydration-warning suppression. | frontend/src/app/globals.css, app pages, components/Layout.tsx |
| 66–67 | Removed unused dependencies/imports and duplicate methods; typed frontend boundary; rewrote misleading/mojibake documentation. Retained compatible legacy metadata tables, explicitly outside active feature promises. | ruff.toml, frontend/eslint.config.mjs, docs, README |
| 68 | Removed unsupported MIT grant; recorded uncertain licensing and preserved third-party rights. Original-source permission remains an owner obligation. | ../LICENSE-STATUS.md, THIRD_PARTY.md, PROVENANCE.md |
| 69 | Added original FC icon, CI and browser workflow. Desktop/mobile screenshots are generated from the synthetic browser workflow. No SEO crawler files or fabricated benchmarks are required for this private-login prototype. | frontend/src/app/icon.svg, .github, frontend/tests |
| 70 | External: create a truthful profile README, professional links/pins and verify activity visibility through GitHub. No fabricated activity or resume impact. | GitHub account |

## External obligations

- Establish original source, permission/license and actual personal contributions. Do not erase historical attribution or rewrite history to conceal imports.
- Update profile/repository settings through the owning GitHub account. No resume was supplied, so resume consistency could not be verified.
- Redeploy through verified hosting accounts, set real domains/origins/secure cookies and verify storage/backup recovery. Existing public deployments are not changed by this branch.
- Run Docker/PostgreSQL integration on a host with Docker and exercise CI on GitHub. Local SQLite checks do not prove these deployments.
- Supply licensed representative cloud billing data and labeled anomalies for genuine predictive evaluation. No synthetic test result proves business savings.
- Verify live Gemini behavior, billing cost and provider account limits with an authorized API key. Offline/mock checks do not prove provider compatibility.

## Suggested GitHub settings

Description: `Cloud billing investigation prototype: FOCUS CSV/Parquet ingestion, spend analytics, anomaly flags, forecast backtests and human-reviewed evidence workflows.`

Topics: `finops`, `focus`, `cloud-cost`, `python`, `fastapi`, `duckdb`, `nextjs`, `forecasting`, `anomaly-detection`, `portfolio-project`.

Bio: `Building Python backend and cloud-cost analytics projects. Exploring data engineering, forecasting and evidence-based FinOps.`

A profile README draft is provided in PROFILE_README.md. Apply it to `omkark2404/omkark2404/README.md` through the owning account; this branch does not create that external repository.

Only add skills and professional links you can substantiate. Do not invent a LinkedIn URL, original-author claim or user/impact metric.

## Local verification (17 October 2026)

- Python 3.12: 46 tests pass, including real HTTP authorization/isolation, ingestion/deletion, persisted reviews/scenarios, numeric grounding/redaction, migration adoption, decimal credits and causal forecasting checks.
- Ruff lint and formatting checks pass. Frontend ESLint, TypeScript and a clean Next.js production build pass without bypasses.
- The production-build browser workflow passes in Chromium: login, reload, two uploads, same-tab dataset switching, spend inspection, persisted review, hypothetical scenario, 390px dashboard overflow check and deletion of both datasets. No page JavaScript errors were observed. Desktop/mobile screenshots use labeled synthetic fixtures.
- npm audit and pip-audit report no known vulnerabilities in the checked dependency locks on this date. This is not a security certification.
- Environment initialization generates private secrets, preserves an existing file and uses mode 0600. The evaluation CLI executes/serializes finite results on a labeled synthetic engineering fixture; no real-data quality claim follows.
- ESLint 9 is retained for the current accessibility plugin peer compatibility; its registry package is deprecated. Upgrade the lint stack together when compatible. Dependency audits currently report no known vulnerability in this stack.
- One upstream Starlette TestClient deprecation warning remains; it does not fail tests. Nonconvergent Holt-Winters candidates are excluded and recorded rather than silently accepted.
- Docker/PostgreSQL containers, live Gemini, real-data predictive accuracy, hosted deployment and GitHub CI have not been executed here. No Docker engine or provider credentials were available.
- Remote publishing was attempted with a dry run and failed because GitHub authentication was unavailable. The local branch is `fix/audit-remediation`; no remote/main/deployment change is implied.

Review the entire branch before merging. Back up pre-existing metadata and billing files before applying migrations. This intentionally changes auth/API contracts and removes unsupported feature claims.

## Follow-up verification, 17 October 2026

- A pinned, CC BY 4.0 public billing sample was evaluated end to end: 10,000 rows, USD 151.43 independently reconciled. The six-day forecast WAPE is 80.1%; naive MAE is not improved. This adds genuine evidence and exposes weak predictive performance rather than resolving it by assertion. See EVALUATION.md and evaluation/public-focus-10000.json.
- Added an actual loopback HTTP integration checker; it passed against a freshly started SQLite backend. Health now reports the actual database dialect. `.github/workflows/integration.yml` will build Docker images and require a PostgreSQL-backed pass on GitHub; Docker/PostgreSQL remain unexecuted here because no engine is available.
- Added a one-call live Gemini verifier and opt-in secret-backed CI job. Missing credentials fail explicitly. No API key was available here, so live success is still unverified. The configurable default model follows current provider guidance.
- The maintainer confirmed external source origin and said they no longer have the source URL. Rights clearance cannot be manufactured; see updated PROVENANCE.md and LICENSE-STATUS.md.
- Profile bio/topics/pins/README changes remain prepared but unapplied: the GitHub plugin is not connected and CLI credentials are unavailable. No public account setting or live deployment has been modified.

- Follow-up public-source investigation located a matching application repository. Twenty-seven pre-remediation files match exactly; the checked tree has no standalone LICENSE/NOTICE and no detected GitHub license. The exact import revision/original copyright holder/permission remain unresolved. The matching README asserts MIT but links to a missing LICENSE file. That assertion is recorded without inventing the absent copyright notice. This third-party reference is retained in PROVENANCE and THIRD_PARTY; current ownership/branding fields remain Omkar's.

Exact pending account edits are in PROFILE_SETTINGS.json: display name, bio, topics, description, profile README target and one additional FinOps pin. It explicitly records that these edits are prepared, not applied. Existing pins are not silently removed.

## Four additional edge cases corrected

- Atomic owner/file uniqueness: model index plus migration 0003; a forced-precheck race test sends two simultaneous HTTP uploads and verifies exactly one 200, one 409, one dataset/Parquet and no raw-upload leftovers. Rollback handling uses the captured owner identity rather than an expired ORM object.
- Early schema limits: CSV header/record/row-width preflight and Parquet metadata checks reject oversized schemas before Pandas loading. Tests replace the Pandas loaders with failure sentinels to prove rejection occurs first; quoted commas/newlines/BOM input still parses.
- Canonical-name collisions: duplicate headers and raw/canonical aliases are rejected explicitly, including an HTTP regression returning 400 rather than TypeError/500.
- Dataset-scoped mutation responses: late approval/scenario success, error, refresh and completion callbacks cannot update a different dataset. Locally handled errors do not raise a stale global banner; authentication failures still follow the session-expiry path. Four browser tests keep a newer dataset's operation pending while releasing the older success/error response.

Validation: 58 backend tests and five browser tests pass. The five include the complete real HTTP browser workflow plus four controlled response-race checks. ESLint/TypeScript and a production build are checked separately. The optional serverless Chromium fallback uses a fresh browser per test; standard Playwright/CI keeps its normal fixtures.

These changes do not establish Docker/PostgreSQL execution, live Gemini access, source-license clearance or GitHub account publishing. Those earlier external verification limits still apply.
