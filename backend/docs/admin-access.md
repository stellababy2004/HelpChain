# Admin Access (DB-backed)

Admin login is DB-based (`AdminUser`), not an ENV runtime secret.

Login URLs:
- Primary: `/admin/login`
- Secondary (ops-only): `/admin/ops/login`

## Environment separation

- Local admin credentials live in the local SQLite workflow and affect only the local DB selected by the local runtime guard.
- Production admin credentials live in Render environment variables and affect only the production database used by Render/Neon.
- These are separate environments. Resetting one does not change the other.

## Local admin flow

Use the local-only reset flow from the repository root:

```powershell
$env:ADMIN_PASSWORD="(your-local-admin-password)"
.\.venv\Scripts\python.exe .\scripts\reset_admin_local.py --confirm-canonical-db
```

Local notes:
- This affects only the canonical local DB after the local DB guard passes.
- It does not affect Render or Neon production credentials.
- If the runtime DB target is unclear, run `.\.venv\Scripts\python.exe .\scripts\print_runtime_info.py` first.

## Production admin flow

Production admin bootstrap runs from Render startup via `backend/scripts/ensure_render_admin.py`.

Required Render environment variables:
- `ADMIN_SEED_USERNAME`
- `ADMIN_SEED_EMAIL`
- `ADMIN_SEED_PASSWORD`
- Optional: `ADMIN_SEED_ROLE`

Production notes:
- This flow affects only the production database configured for the Render service.
- It does not reset any local SQLite admin password.
- Operators should rotate/set the values in Render, then restart/redeploy the service.

## Local runtime recovery flow

`backend/scripts/ensure_admin.py` is a local/runtime recovery helper for the effective local runtime DB only.

```powershell
$env:ADMIN_SEED_USERNAME="admin"
$env:ADMIN_SEED_PASSWORD="(your-local-runtime-password)"
$env:ADMIN_SEED_EMAIL="admin@helpchain.live"
python backend\scripts\ensure_admin.py --confirm-canonical-db
```

Runbook:
- `200` on `/admin/login` but local login fails -> verify local DB target first, then use the local flow only.
- `200` on production `/admin/login` but production login fails -> update Render env vars and rerun the production bootstrap via restart/redeploy.
- `500` on admin routes in production -> check Render/server logs first.
- `403` on admin routes -> check role/allowlist and cookies/session state.

Audit trail note:
- `/admin/audit` is admin-only and stores IP + user-agent for traceability.
- Recommended retention window for audit events: 90 days.

