# HelpChain (backend)

[![CI – Lint • Security • Tests](https://github.com/stellababy2004/HelpChain.bg/actions/workflows/ci.yml/badge.svg)](https://github.com/stellababy2004/HelpChain.bg/actions/workflows/ci.yml)
![Python Version](https://img.shields.io/badge/python-3.11%20|%203.12-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## Releases

### v0.1.0 — 2025-09-29

Initial test-stable release — 13 passing tests.

#### Highlights

- Тестовете са рефакторирани и стабилизирани (mocked HTTP за чатбот).
- Welcome email тестът е направен безопасен чрез mock на SMTP.
- Добавен conftest.py с фикстури и PYTHONPATH корекция за test пакетите.
- Добавен LICENSE (MIT) и tag `v0.1.0`.
- Pre-commit hooks (black, ruff и др.) вкарани в CI локално.

## Седмичен отчет — 2025-10-28

- Активирахме конфигурируем `VOLUNTEER_OTP_BYPASS` и директно активиране на сесията, така че доброволците да влизат без SMS код при нужда.
- Добавихме примерен доброволец в `init_db.py` и направихме скрипта repeatable за демонстрации и локални тестове.
- Пренасочихме навигацията във `volunteer_dashboard` към секционни котви, което спря пренасочванията към липсващи маршрути и подобри UX.
- Преработихме администраторските табла (`admin_dashboard.html`, `admin_analytics_professional.html`) с нови карти, живи метрики и по-бързи заявки.
- Добавихме Celery задача `generate_sample_analytics` и модул `analytics_sample_data.py`, за да пълним автоматично аналитичните таблици.
- Вкарахме новия WebSocket клиент `helpchain-websocket.js` и service worker `sw.js` за стабилни real-time връзки и офлайн кеширане.
- Разширихме локализацията: нов език (FR), обновени `messages.po/.pot`, езиков селектор в навигацията и обновен `init_multilingual.py`.
- Утвърдихме конфигурацията – root `.env.example` и `backend/helpchain_backend/src/config.py` описват Postgres setup, а уеб push модулът показва ясни fallback-и при липсващ VAPID ключ.

## Deployment snippets

### Nginx static cache

A ready-to-use nginx snippet for serving static assets with sensible cache headers is provided at `deploy/nginx_static_cache.conf`.

Include it in your site configuration (for example, inside your server block):

```nginx
include /path/to/your/repo/deploy/nginx_static_cache.conf;
```

The snippet configures:

- Long-lived, `immutable` caching for fingerprinted assets (e.g. `app-abcdef12.js`).
- A shorter default TTL for other `/static/` files.

Adjust the regex in the snippet if your build artifacts use a different fingerprint naming convention.

## Quick Start

### Manual Run (single entry point)

From the repository root, the canonical entry point is `run.py`:

```pwsh
python run.py
```

Service worker cache note:

- The app registers a service worker at `/sw.js`.
- The homepage uses network-first and `no-store` headers to avoid stale HTML.
- If you ever see an old landing page after a deploy, unregister SW and hard refresh:
  - DevTools → Application → Service Workers → Unregister, then `Ctrl+Shift+R`.
  - Or in Console:
    ```js
    navigator.serviceWorker
      .getRegistrations()
      .then((rs) => rs.forEach((r) => r.unregister()));
    caches
      .keys()
      .then((keys) => Promise.all(keys.map((k) => caches.delete(k))));
    ```

### Quick Smoke Test (FTS + Role-based Email Search)

Environment knobs:

- `HELPCHAIN_BASE_URL` (default `http://127.0.0.1:5000`)
- `HELPCHAIN_JWT_SECRET` (must match backend; default `change-me`)

Expected behavior:

- `q=clinic` matches seeded rows (FTS when SQLite available).
- Email queries like `q=@example.com` match for `admin` token, but not for `user` token.

### Diagnostics Endpoints

Health (no auth):

```pwsh
Invoke-RestMethod http://127.0.0.1:5000/api/_health
```

Example response:

```json
{ "status": "ok", "ok": true, "uptime_seconds": 42 }
```

FTS Status (JWT required):

```pwsh
$login = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5000/api/login `
	-Body (@{username='admin';password='secret123'} | ConvertTo-Json) `
	-ContentType 'application/json'
$token = $login.access_token
Invoke-RestMethod -Headers @{Authorization="Bearer $token"} `
	http://127.0.0.1:5000/api/_fts_status
```

Example response (SQLite):

```json
{
  "engine": "sqlite",
  "fts_enabled": true,
  "help_requests_count": 3,
  "sqlite_version": "3.45.2",
  "fts_triggers_present": {
    "help_requests_ai": true,
    "help_requests_au": true,
    "help_requests_ad": true
  },
  "fts_rows": 3
}
```

Notes:

- `/api/_health` is not rate limited and does not require auth.
- `/api/_fts_status` requires JWT auth but is not rate limited; only `/api/login` and `/api/requests` use rate limiting.

### Troubleshooting

- Verify FTS status quickly:
  - Call `/api/_fts_status` (see above). Check `engine`, `fts_enabled`, `fts_rows`, and `fts_triggers_present`.
- Rebuild the FTS index (SQLite):
  - Use the helper script:
    ```pwsh
    python scripts/fts_rebuild.py
    ```
  - After rebuild, confirm with:
    ```pwsh
    $login = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5000/api/login `
    	-Body (@{username='admin';password='secret123'} | ConvertTo-Json) `
    	-ContentType 'application/json'
    Invoke-RestMethod -Headers @{Authorization="Bearer $($login.access_token)"} `
    	http://127.0.0.1:5000/api/_fts_status
    ```
- No search matches when expected:
  - Ensure you’re using the `q=` param and SQLite has FTS5. If `fts_enabled` is false, the API falls back to LIKE; email field is never matched for non-privileged roles.
  - Privileged email search requires a privileged token (e.g., `admin`). Non-privileged users will not match on `email`.
- 401 Unauthorized on endpoints:
  - Static `devtoken` is deprecated. Use real JWT via `/api/login`.
  - Local seeded users: `admin/secret123` (privileged), `testuser/secret123` (non-privileged).
- Reset local DB (fresh start):
  - Stop the server, then delete the SQLite file and restart:
    ```pwsh
    Remove-Item .\instance\volunteers.db -Force
    python ..\run.py
    ```
  - Seeds and FTS structures are recreated automatically on startup.

### Local setup and startup

From the `backend` directory, use the canonical root dependency manifest and entrypoint:

```pwsh
pip install -r ..\requirements.txt
python ..\run.py
```

Visit: `http://127.0.0.1:5000/demo/volunteers` for the volunteer dashboard demo.

## Configuration

### 1. Secrets & Environment Loading

The canonical application environment template is `.env.example` at the repository root. Copy it to `.env` at the repository root; the application loads that root `.env` via `python-dotenv`.

`SECRET_KEY` should be set to a strong random value. A development-only fallback is used when it is absent.

Generate a strong key:

```pwsh
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Add it to the repository-root `.env`:

```dotenv
SECRET_KEY=your_long_random_value_here
```

You can still use a transient shell value for quick tests:

```pwsh
$env:SECRET_KEY = "your_long_random_value_here"
python ..\run.py
```

### 2. Sample `.env` Variables

From the `backend/` directory, create the local root `.env` from the canonical template:

```pwsh
Copy-Item ..\.env.example ..\.env
```

Review the placeholder values in `../.env` before starting the application with the root dependencies and entry point shown above.

### 3. Database Selection

The canonical application is started from the repository root with `python run.py`. Local database selection is controlled by the root environment and `backend/helpchain_backend/src/config.py`.

Switch to Postgres:

```pwsh
$env:DATABASE_URL = 'postgresql+psycopg://user:pass@host/dbname'
python ..\run.py
```

Run migrations from the repository root with the canonical application and migration directory:

```pwsh
Set-Location ..
python -m flask --app run:app db migrate --directory migrations -m "add field"
python -m flask --app run:app db upgrade --directory migrations
```

### 4. Locale Selection Logic

`_select_locale()` chooses language in this order:

1. Cookie `language` if valid (`bg`, `fr`, `en`).
2. Geo/IP header (`CF-IPCountry`, `X-AppEngine-Country`, etc.): `FR->fr`, `BG->bg`, other -> `en`.
3. `Accept-Language` best match.
4. Fallback to configured default (`fr`).

To force a language cookie for manual testing:

```pwsh
Invoke-WebRequest http://127.0.0.1:5000/set_language?language=bg | Select-Object -ExpandProperty StatusCode
```

### 5. Rate Limiting

Adjust request limits (defaults 60/60s) via:

```pwsh
$env:HELPCHAIN_RATE_LIMIT='100'
$env:HELPCHAIN_RATE_WINDOW='120'
python ..\run.py
```

Headers surfaced when throttled: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Window`, `Retry-After`.

### 6. JWT Auth Recap

Obtain token:

```pwsh
$login = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5000/api/login -Body (@{username='admin';password=$env:ADMIN_USER_PASSWORD} | ConvertTo-Json) -ContentType 'application/json'
$token = $login.access_token
```

Use:

```pwsh
Invoke-RestMethod -Headers @{Authorization="Bearer $token"} http://127.0.0.1:5000/api/requests
```

### 7. Regenerating / Resetting Local Data

```pwsh
Remove-Item .\instance\volunteers.db -Force
python ..\run.py
```

### 8. Security Checklist (Dev vs Prod)

| Item                   | Dev                    | Prod                          |
| ---------------------- | ---------------------- | ----------------------------- |
| Secret key rotation    | Optional               | Required (on compromise)      |
| Cookie `SameSite`      | Lax                    | Lax/Strict depending on flows |
| HTTPS                  | Optional (localhost)   | Mandatory                     |
| Admin default password | Keep for local scripts | Change & store in vault       |
| `session_debug` route  | Removed                | Must stay removed             |
| Service worker caching | Active                 | Review cache strategy         |

### 9. Troubleshooting Secrets

If `echo $env:HELPCHAIN_SECRET_KEY` shows nothing but the app still runs with your key, it is because the key comes from `.env` (loaded inside Python) not your shell. Confirm via:

```pwsh
python -c "from dotenv import load_dotenv; load_dotenv(); import os; print(os.getenv('HELPCHAIN_SECRET_KEY'))"
```

### 10. Generating Strong Values in Bulk

```pwsh
1..3 | ForEach-Object { python -c "import secrets; print(secrets.token_urlsafe(48))" }
```

Store final secrets only in `.env` or vault; avoid committing `.env`.

### Volunteer Dashboard (Requests UI)

Route: `/demo/volunteers` serves the dashboard. It calls `/api/requests` (now JWT protected) with pagination, filtering, full-text search, multi-column sorting and ETag-based caching.

Pagination:
`page` (int, default 1), `page_size` (int, default 20, max 100)

Filters:
`status` (pending|in_progress|completed|rejected), `city`, `category`

Search:
`q` (search text). On SQLite, the API uses FTS5 across `title`, `description`, `message`, `city`, `region`, `name` — and `email` only for privileged roles. On other databases, it falls back to case-insensitive LIKE across the same allowed fields.

Base response:

```json
{
  "data": [
    {
      "id": "HR-12",
      "created_at": "2025-11-13",
      "city": "Paris",
      "category": "Administrative",
      "requester": "Marie",
      "status": "NEW",
      "priority": "NORMAL"
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 47,
  "total_pages": 3,
  "etag": "9f1d..."
}
```

Detail: `GET /api/requests/<id>` now returns masking plus (conditionally) real contact fields:

```json
{
  "id": 12,
  "status": "NEW",
  "email_masked": "m***@example.com",
  "phone_masked": "*******42",
  "email": "full@example.com", // only if privileged role
  "phone": "+33123456742" // only if privileged role
}
```

Fallback: if the dashboard runs without backend or receives network errors it swaps to an embedded mock array (visual hint: tag color changes).

### JWT Auth & Login

Static bearer token was replaced with real JWT flow:

`POST /api/login` body:

```json
{ "username": "admin", "password": "secret" }
```

Response:

```json
{
  "access_token": "<JWT>",
  "token_type": "Bearer",
  "expires_in": 3600,
  "role": "admin"
}
```

Include header for all protected endpoints:
`Authorization: Bearer <access_token>`

Privileged roles (unmask contact data): `admin`, `superadmin`, `moderator`.

Also for search, only privileged roles match on the `email` field; non-privileged queries never match emails.

PowerShell example:

```pwsh
$login = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5000/api/login -Body (@{username='admin';password='secret'} | ConvertTo-Json) -ContentType 'application/json'
$token = $login.access_token
Invoke-RestMethod -Headers @{Authorization="Bearer $token"} "http://127.0.0.1:5000/api/requests?page=1&page_size=10"
```

### Multi-Column Sorting

Old: `sort=<field>&order=<asc|desc>` (single column).

New: `sort=<list>` where `<list>` is comma-separated column names; prefix with `-` for descending.

Supported columns: `created_at`, `priority`, `city`, `status`, `category`, `title`, `id`.

Examples:

```pwsh
# Sort by city ascending then priority descending
Invoke-RestMethod -Headers @{Authorization="Bearer $token"} "http://127.0.0.1:5000/api/requests?sort=city,-priority"

# Default (created_at desc) explicitly
Invoke-RestMethod -Headers @{Authorization="Bearer $token"} "http://127.0.0.1:5000/api/requests?sort=-created_at"
```

### ETag Caching

List endpoint computes an ETag hash of query parameters + latest update timestamp. Client can send `If-None-Match` to avoid transferring unchanged pages.

PowerShell example (conditional request):

```pwsh
$resp = Invoke-RestMethod -Headers @{Authorization="Bearer $token"} "http://127.0.0.1:5000/api/requests?page=1&page_size=10&sort=-created_at"
$etag = $resp.etag
Invoke-WebRequest -Headers @{Authorization="Bearer $token"; 'If-None-Match'=$etag} "http://127.0.0.1:5000/api/requests?page=1&page_size=10&sort=-created_at" | Select-Object -ExpandProperty StatusCode
```

If status code = 304, re-use previously cached `data`.

### Rate Limiting

Endpoints `/api/login` and `/api/requests` are protected with a sliding-window rate limiter (defaults: 60 requests per 60s per IP). When throttled, the server responds with `429 Too Many Requests` and headers:

- `X-RateLimit-Limit`: total allowed in window
- `X-RateLimit-Remaining`: remaining requests in current window
- `X-RateLimit-Window`: window duration in seconds
- `Retry-After`: seconds until next attempt (advisory)

Tune via environment variables:

```pwsh
$env:HELPCHAIN_RATE_LIMIT = '60'
$env:HELPCHAIN_RATE_WINDOW = '60'
python ..\run.py
```

### Privacy Masking (Updated)

Detail endpoint always returns masked fields; raw `email` / `phone` only included for privileged roles. Non-privileged clients simply get `null` for those raw fields.

Email mask: first char + `***@domain`.
Phone mask: all but last 2 digits replaced by `*`.

### Dashboard JS Behavior

- Stores JWT in `localStorage.HELPCHAIN_JWT`.
- Adds `If-None-Match` when an ETag is known.
- Shift+Click table headers to append sorting columns; plain click resets to single-column.
- Modal detail view shows both masked and (if authorized) real contact data.

### Database & Migrations

Database configuration comes from the root `.env` and `backend/helpchain_backend/src/config.py`. Use the `postgresql+psycopg://` dialect for PostgreSQL.

Run Flask-Migrate from the repository root against the canonical application and migration directory:

```pwsh
python -m flask --app run:app db migrate --directory migrations -m "example"
python -m flask --app run:app db upgrade --directory migrations
```

To run locally against PostgreSQL from the repository root:

```pwsh
$env:DATABASE_URL='postgresql+psycopg://user:pass@host/dbname'
python run.py
```

### Model Mapping

Dashboard rows map to `HelpRequest`:

- `id` -> prefixed as `HR-<numeric>`
- `status` internal values (pending/in_progress/completed/rejected) mapped to UI (NEW/IN_PROGRESS/COMPLETED/REJECTED)
- `priority` enum -> upper-case displayed
- `title` -> `category` in dashboard terminology
- `name` -> `requester`

### (Deprecated) Single-Column Sorting

Previous `sort=<field>&order=<asc|desc>` API remains backward-compatible but dashboard now uses the multi-column format. Prefer the new comma list going forward.

### Role-Based Contact Access

Use JWT role claim; privileged roles see `email` / `phone` fields else they are `null`. Mask fields always present for UI consistency.

### Extending

- Add new filter? Extend the canonical `/api/requests` route implementation.
- Add sorting? Accept `sort=created_at|priority` and append `order_by` before pagination.
- Replace Bearer with JWT? Verify token, extract subject, then scope queries (e.g. only assigned volunteer requests).

### Full-Text Search Details

- Backend auto-initializes an FTS5 virtual table `help_requests_fts` with external content bound to `help_requests(id)` and keeps it in sync via triggers (AFTER INSERT/UPDATE/DELETE).
- Search field set: `title`, `description`, `message`, `city`, `region`, `name` for all users; `email` is included only for privileged roles.
- Query param `q` is tokenized by spaces; each token is matched with prefix search (`token*`) and all tokens must match across any allowed field.
- If FTS5 is unavailable (non-SQLite or SQLite without FTS5), search falls back to case-insensitive LIKE across the same allowed fields.

Ranking and ordering:

- When `q` is present and FTS5 is active, results are ranked via `bm25(help_requests_fts)` and ordered by rank first (lower is better), then by any user-provided sort columns.
- Without `q`, ordering is controlled solely by the `sort` parameter (default: `-created_at`).

Indexes:

- `status`, `city`, `region`, `assigned_volunteer_id`, `completed_at`, `source_channel` are indexed in the model.
- `created_at` is indexed to improve sorting/pagination performance.

### Known Limitations

- ETag invalidation uses max(updated_at); heavy concurrent writes could benefit from version columns or incremental page hashes.
- Authentication currently 1h fixed expiry; implement refresh tokens or sliding expiration for production.
