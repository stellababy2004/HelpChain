# Local DB Canonical Policy

## Canonical local app
- `backend.appy:app`

## Canonical local DB
- `sqlite:///C:/dev/HelpChain.bg/backend/instance/app_clean.db`

## Rule
- Local DB write scripts must:
  - print preflight (`APP`, `DB`)
  - refuse non-canonical DB targets
  - require explicit manual confirmation flag (`--confirm-canonical-db`)

## Read-only diagnostics (safe)
- `.\.venv\Scripts\python.exe .\scripts\print_runtime_info.py`
- `powershell -ExecutionPolicy Bypass -File .\scripts\dev_doctor.ps1`
- `powershell -ExecutionPolicy Bypass -File .\scripts\go_no_go.ps1`
- `powershell -ExecutionPolicy Bypass -File .\scripts\test_smoke.ps1`

## Legacy/non-canonical SQLite files
- `instance/hc_local_dev.db`
- `instance/volunteers.db`
- `instance/app.db`
- `instance/hc_run.db`

These files are not canonical targets for local write workflows.

## Troubleshooting
- If runtime DB differs from canonical, stop write operations.
- Run runtime diagnostics first and fix environment/app launch target.
