# DEV Rules (Local)

## Canonical Flask App
- Use only: `backend.appy:app`

## Official Local Start Command
- `\.venv\Scripts\python.exe -m flask --app backend.appy:app run --host 127.0.0.1 --port 5005`
- Preferred wrapper: `powershell -ExecutionPolicy Bypass -File .\scripts\run_local.ps1`

## Official Runtime Info Command
- `\.venv\Scripts\python.exe .\scripts\print_runtime_info.py`

## Official Admin Reset Command
- `\.venv\Scripts\python.exe .\scripts\reset_admin_local.py`

## Drift Prevention Rules
- Do not use temporary SQLite files for local dev.
- Do not run the app through any other module path.
- Before DB-sensitive operations (admin reset, migrations, recompute scripts), run runtime info first and verify target DB.

## DATABASE SAFETY RULES
- Codex is not allowed to run automatic DB write operations.
- Codex must never execute write operations against local DB without explicit manual user action.
- Codex must never change `SQLALCHEMY_DATABASE_URI` without explicit user permission.

### Manual-Only Operations (User must run manually)
- Any Alembic migration command:
  - `flask db upgrade`
  - `flask db downgrade`
  - `flask db stamp`
  - `flask db revision`
- Any schema creation/destruction operation:
  - `db.create_all()`
  - `db.drop_all()`
- Admin credential reset/bootstrap:
  - `.\.venv\Scripts\python.exe .\scripts\reset_admin_local.py`
- Any recompute/backfill script that writes to DB.
- Any direct SQL `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`.

### Read-Only Safe Scripts (Allowed for diagnostics)
- `powershell -ExecutionPolicy Bypass -File .\scripts\run_local.ps1` (startup/runtime visibility only)
- `.\.venv\Scripts\python.exe .\scripts\print_runtime_info.py`
- `powershell -ExecutionPolicy Bypass -File .\scripts\dev_doctor.ps1`
- `powershell -ExecutionPolicy Bypass -File .\scripts\test_smoke.ps1`
- `powershell -ExecutionPolicy Bypass -File .\scripts\go_no_go.ps1`

### Enforcement
- If DB target is unclear, stop and request confirmation before any DB-sensitive action.
- Prefer read-only diagnostics first, then manual user-triggered DB writes only.
- See also: `DB_WRITE_OPERATIONS_MANUAL_ONLY.md`.

### Seed/Demo Guardrail
- Demo/seed scripts may write only to canonical local DB:
  - `sqlite:///C:/dev/HelpChain.bg/backend/instance/app_clean.db`
- If runtime DB target is different, scripts must refuse automatically and exit non-zero.

### Legacy SQLite Paths (Non-Canonical)
- `instance/hc_local_dev.db`
- `instance/volunteers.db`
- `instance/app.db`
- `instance/hc_run.db`
- These files are legacy/local artifacts and must not be used for local write workflows.
