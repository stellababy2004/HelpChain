# CI / CD Policy – HelpChain

HelpChain uses a strict CI pipeline designed to prevent
schema drift, orphan data and unstable deployments.

## CI Steps (mandatory)

1. Init test database (SQLite)
2. Schema Drift Guard (ORM vs real DB)
3. CRUD Smoke Tests (rollback)
4. Pytest (unit + integration)

Any failure blocks the pipeline.

## Why this matters

- Prevents silent DB/model divergence
- Guarantees reproducible environments
- Safe for long-term institutional use
