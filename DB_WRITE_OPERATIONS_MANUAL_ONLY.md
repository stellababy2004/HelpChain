# DB Write Operations - Manual Only

This project uses strict local DB safety rules.

## Core Rule
- Codex must not execute automatic DB write operations.
- DB writes are manual-only and must be explicitly triggered by the user.

## Forbidden for Codex (without explicit manual user action)
- Alembic migration execution:
  - `flask db upgrade`
  - `flask db downgrade`
  - `flask db stamp`
  - `flask db revision`
- SQLAlchemy schema creation/destruction:
  - `db.create_all()`
  - `db.drop_all()`
- Admin reset/bootstrap writes:
  - `.\.venv\Scripts\python.exe .\scripts\reset_admin_local.py`
- Recompute/backfill scripts that update data.
- Direct SQL write/destructive commands (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`).

## Config Protection
- `SQLALCHEMY_DATABASE_URI` must not be modified by Codex without explicit user permission.
- Canonical local DB for manual writes is fixed to:
  - `sqlite:///C:/dev/HelpChain.bg/backend/instance/app_clean.db`

## Read-Only Safe Diagnostics
- `.\.venv\Scripts\python.exe .\scripts\print_runtime_info.py`
- `powershell -ExecutionPolicy Bypass -File .\scripts\dev_doctor.ps1`
- `powershell -ExecutionPolicy Bypass -File .\scripts\go_no_go.ps1`
- `powershell -ExecutionPolicy Bypass -File .\scripts\test_smoke.ps1`

## Mandatory Pre-Check Before DB-Sensitive Work
- Confirm canonical app entrypoint: `backend.appy:app`
- Confirm current `SQLALCHEMY_DATABASE_URI`
- If DB target is unclear: stop and request confirmation.

## Canonical Refusal Rule
- Local write-capable scripts must print DB preflight (`APP`, `DB`) and refuse non-canonical targets.
- Local write-capable scripts must require explicit manual confirmation flag (for example `--confirm-canonical-db`) before write.
