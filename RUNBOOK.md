# Local Runbook

Short local startup and infrastructure inventory for this workspace.

Secrets are intentionally not copied into this file. Use the source locations below to inspect them locally if you have permission.

## Start

From `C:\dev\HelpChain.bg`:

```powershell
.\.venv\Scripts\Activate.ps1
.\start_local.ps1
```

Expected local behavior:

- Primary DB candidate: `instance\hc_local_dev.db`
- Fallback DB candidate: `backend\instance\app_clean.db`
- If the primary DB is unhealthy, the launcher falls back automatically to `backend\instance\app_clean.db`
- App URL: `http://127.0.0.1:5000`

## Stop

If running in the foreground:

```powershell
Ctrl+C
```

If running in the background:

```powershell
Stop-Process -Id <PID>
```

## Verify

```powershell
Invoke-WebRequest http://127.0.0.1:5000/
Invoke-RestMethod http://127.0.0.1:5000/api/_health
```

## Login Entry Points

- Admin login: `http://127.0.0.1:5000/admin/login`
- Ops login: `http://127.0.0.1:5000/admin/ops/login`

Admin auth is DB-backed through `AdminUser`, not a single runtime secret.

If you need to seed or reset a local admin account, use:

```powershell
$env:ADMIN_SEED_USERNAME = "<username>"
$env:ADMIN_SEED_PASSWORD = "<strong-password>"
$env:ADMIN_SEED_EMAIL = "<email>"
python backend\scripts\ensure_admin.py
```

Force reset:

```powershell
$env:ADMIN_SEED_USERNAME = "<username>"
$env:ADMIN_SEED_PASSWORD = "<strong-password>"
$env:ADMIN_SEED_FORCE_RESET = "1"
python backend\scripts\ensure_admin.py
```

## Infrastructure Inventory

| Service | Address / Endpoint | Credential source | Notes |
| --- | --- | --- | --- |
| Flask app | `http://127.0.0.1:5000` | none | Local launcher entrypoint |
| Local app alias | `http://localhost:5000` | none | Allowed by local CORS |
| Health endpoint | `http://127.0.0.1:5000/api/_health` | none | No-auth health check |
| Admin UI | `http://127.0.0.1:5000/admin/login` | DB-backed `AdminUser` | Primary admin login |
| Ops UI | `http://127.0.0.1:5000/admin/ops/login` | DB-backed `AdminUser` | Secondary ops login |
| SQLite primary | `C:\dev\HelpChain.bg\instance\hc_local_dev.db` | none | Preferred local DB file |
| SQLite fallback | `C:\dev\HelpChain.bg\backend\instance\app_clean.db` | none | Launcher fallback DB |
| SMTP | `smtp.zoho.eu:587` | `.env` -> `MAIL_USERNAME`, `MAIL_PASSWORD` | TLS on, SSL off in this workspace |
| Redis / Celery broker | `redis://localhost:6379/0` | `REDIS_URL` or `CELERY_BROKER_URL` | Used only if workers are started |
| Redis / Celery result backend | `redis://localhost:6379/0` | `REDIS_URL` or `CELERY_RESULT_BACKEND` | Used only if workers are started |
| Redis / rate limiting | `redis://localhost:6379/1` | `REDIS_URL` | Default perf config fallback |
| Resend API | `https://api.resend.com/emails` | `RESEND_API_KEY` | Optional outbound mail path |
| Ollama | `http://localhost:11434/api/generate` | no key by default | Used only if `OLLAMA_MODEL` is set |
| OpenAI API | provider-driven | `OPENAI_API_KEY` | Optional AI provider |
| Gemini API | provider-driven | `GEMINI_API_KEY` | Optional AI provider |
| e-Sante FHIR | `https://gateway.api.esante.gouv.fr/fhir` | `.env` -> `ESANTE_API_KEY` | Import/enrichment scripts |
| Annuaire Sante FHIR v2 | `https://gateway.api.esante.gouv.fr/fhir/v2` | `.env` -> `ESANTE_API_KEY` | Import script default |
| Plausible script | `https://plausible.io/js/script.js` | none | Used only if enabled |
| Sentry | DSN-defined | `SENTRY_DSN` | Optional; disabled if unset |

## Runtime Config Knobs

Primary local launcher variables:

- `FLASK_CONFIG=dev`
- `FLASK_DEBUG=0`
- `HC_DB_PATH`
- `SQLALCHEMY_DATABASE_URI`
- `DATABASE_URL`
- `HOST`
- `PORT`

Relevant app config sources:

- root `.env`
- [start_local.ps1](start_local.ps1)
- [backend/helpchain_backend/src/config.py](backend/helpchain_backend/src/config.py)

## Secret Sources

Secrets exist in these places and should not be copied into docs or chat transcripts:

- root `.env` for local DB/mail/e-Sante values
- process environment for optional integrations such as OpenAI, Gemini, Redis, Sentry, Resend
- local DB `admin_users` table for DB-backed admin accounts
- dev/demo seed scripts:
  - `backend/scripts/dev_bootstrap.py`
  - `backend/scripts/seed_operator_visibility_verification.py`

If any of those values were pasted into logs or chat, rotate them.
