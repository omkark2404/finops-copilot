# Architecture

The application is a single-process modular monolith. Next.js calls FastAPI using credentialed requests and HTTP-only cookies. FastAPI checks each dataset's owner; admins have explicit cross-owner access. Mutation roles are separate from authentication.

SQLite is an explicit local mode under DATA_DIR. Compose uses PostgreSQL. Alembic upgrades metadata, including durable workflow evidence. Parquet is the analytical source of truth; no analytical tables are copied into a persistent DuckDB file. Each execution thread owns an in-memory DuckDB connection configured to UTC, two threads and 512 MB query memory.

Heavy functions run outside the HTTP event loop. One analysis runs at a time per process, with a two-second admission wait before a 503. This also serializes analytical deletion. Run exactly one API worker against one local storage directory. This is a bounded prototype strategy, not distributed job processing.

The evidence workflow performs quality, attribution, anomaly, candidate, investigation, scenario-boundary and checklist stages. It returns and persists evidence, recommendations and validation results. Optional LLM output does not own numeric fields or final actions. Saved human decisions and scenarios are audited.

See README for the architecture diagram, DATA for financial semantics, ML for evaluation protocols, and LIMITATIONS for unsupported capabilities.
