# Local Demo Seed

`scripts/seed_local_demo.py` creates a stable local demo dataset against the active HelpChain runtime database. It is intentionally conservative:

- it prints the active DB/runtime configuration before doing anything
- it refuses production-like targets by default
- it only allows SQLite targets unless you explicitly pass `--allow-unsafe-target`
- it tags demo rows with `[LOCAL_DEMO_SEED]` so `--reset-demo` only removes demo-created data

## What It Seeds

- admin accounts: `superadmin`, `admin`, `ops`, `readonly`
- local MFA state for demo admins: `mfa_enabled=False`, no TOTP secret
- structures:
  - `CCAS de Nanterre`
  - `Association Solidarite Paris`
  - `Centre Social Boulogne`
- request and case examples across the major workflow states
- professional leads and demo-page leads
- organization access requests
- notification jobs, request activity, and admin dashboard rows when the corresponding tables exist

If a model exists in code but the active local SQLite schema does not yet contain that table, the script skips it and prints a warning instead of forcing migrations.

## PowerShell

From `C:\dev\HelpChain`:

```powershell
.\.venv\Scripts\python.exe scripts\seed_local_demo.py --dry-run
```

Run the real seed:

```powershell
.\.venv\Scripts\python.exe scripts\seed_local_demo.py
```

Reset only demo-created rows:

```powershell
.\.venv\Scripts\python.exe scripts\seed_local_demo.py --reset-demo
```

## Notes

- The script uses the active app runtime DB, not whichever file you expect manually. Always read the printed `SQLALCHEMY_DATABASE_URI`, `DATABASE_URL`, and `HC_DB_PATH` first.
- When `REQUIRE_ADMIN_MFA=True`, the seeded demo admins are left in a clear local setup state instead of bypassing MFA.
- In this branch, demo leads are visible at `/admin/professional-leads/demo`.
