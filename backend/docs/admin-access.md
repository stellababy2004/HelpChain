# Admin Access (DB-backed)

Admin login is DB-based (`AdminUser`), not an ENV runtime secret.

Stable URL:
- `/admin/login`

After DB restore/reset, if admin account is missing:

```powershell
cd C:\dev\HelpChain.bg
$env:ADMIN_SEED_USERNAME="admin"
$env:ADMIN_SEED_PASSWORD="Admin12345!"
$env:ADMIN_SEED_EMAIL="admin@helpchain.live"
python backend\scripts\ensure_admin.py
```

Notes:
- Script is idempotent: if user already exists, it does nothing.
- Missing `ADMIN_SEED_USERNAME` or `ADMIN_SEED_PASSWORD` -> no-op (safe by default).

Runbook:
- `200` on `/admin/login` but login fails -> run `ensure_admin.py` (`ADMIN_SEED_FORCE_RESET=1` if password reset is required).
- `500` on admin routes -> check Render/server logs first.
- `403` on admin routes -> check role/allowlist and cookies/session state.

Force reset example:

```powershell
$env:ADMIN_SEED_USERNAME="admin"
$env:ADMIN_SEED_PASSWORD="(your-strong-password)"
$env:ADMIN_SEED_FORCE_RESET="1"
python backend\scripts\ensure_admin.py
```
