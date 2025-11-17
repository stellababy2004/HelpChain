# HelpChain Backend – Deployment Guide (Concise)

This document is a shortened operational checklist. For deeper details see `README.md`.

## 1. Prerequisites

- Python 3.12
- Git
- Postgres 14+ (production) or SQLite (dev/demo)
- Optional: Redis (future Celery / rate limit storage)
- Reverse proxy: Nginx (TLS termination + static cache)

## 2. Clone & Setup

```bash
git clone https://github.com/stellababy2004/HelpChain.bg.git
cd HelpChain.bg/backend
python -m venv .venv
source .venv/bin/activate  # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt  # or poetry install
```

## 3. Essential Environment Variables (`.env`)

```dotenv
HELPCHAIN_SECRET_KEY=<STRONG_RANDOM>
DATABASE_URL=postgresql+psycopg://user:pass@host:5432/helpchain
ADMIN_USER_PASSWORD=ChangeMe!12345
MICROSOFT_TENANT_ID=common
MICROSOFT_CLIENT_ID=CHANGE-ME-CLIENT-ID
```

Optional (mail, analytics, external services) are documented in `.env.example`.

## 4. Database Migration (Postgres)

```bash
export FLASK_APP=appy.py
flask db upgrade            # apply existing migrations
# After model change:
flask db migrate -m "add field"
flask db upgrade
```

SQLite (dev): auto-creates `instance/volunteers.db` – no migration command needed.

## 5. Running the App

Development (auto-reload disabled in prod):

```bash
python app.py          # minimal entry
python appy.py         # full entry (migrations, extensions)
```

Production (example Gunicorn):

```bash
gunicorn -w 4 -b 0.0.0.0:8000 app:app       # or appy:app
```

Behind Nginx: proxy `/` to `http://127.0.0.1:8000` and serve `/static/` with cache rules (`deploy/nginx_static_cache.conf`).

## 6. Static Assets & Service Worker

- `sw.js` served at root. On deploy, advise clients to hard refresh if stale.
- Place images/fonts under `backend/static/`.

## 7. Health & Monitoring

Health check (no auth):

```
GET /api/_health  -> {"status":"ok"}
```

Application metrics to extend (suggestion): add Prometheus or stats endpoint later.

## 8. JWT Authentication

Obtain token:

```bash
curl -X POST http://HOST/api/login \
 -H 'Content-Type: application/json' \
 -d '{"username":"admin","password":"Admin12345!"}'
```

Use token:

```bash
curl -H "Authorization: Bearer <token>" http://HOST/api/requests
```

## 9. Rate Limiting (if enabled)

Env overrides:

```bash
HELPCHAIN_RATE_LIMIT=60
HELPCHAIN_RATE_WINDOW=60
```

Returns `429` + `Retry-After` when exceeded.

## 10. Locale Behavior

Order: cookie `language` > IP country header (FR/BG -> fr/bg, others -> en) > `Accept-Language` > default `fr`.
Set cookie manually:

```
GET /set_language?language=bg
```

## 11. Upgrade Procedure

1. Pull changes.
2. Regenerate venv dependencies (if `requirements.txt` changed).
3. Run `flask db upgrade` (Postgres). For SQLite dev: delete file if schema incompatible.
4. Restart Gunicorn / systemd service.
5. Verify `/api/_health` & `/api/requests`.
6. Clear service worker caches if front-end changes (optional).

## 12. Rollback Procedure

1. Checkout previous stable tag/commit.
2. Run `flask db downgrade` to previous revision if destructive migration.
3. Restore DB backup (if needed).
4. Restart service.
5. Validate health & critical endpoints.

## 13. Backups

- DB: daily `pg_dump` + offsite copy.
- Secrets: store in manager (Azure Key Vault / AWS Secrets Manager). Do not rely on `.env` only.
- Logs: rotate (logrotate or journald configuration).

## 14. Security Quick List

| Item           | Action                                                            |
| -------------- | ----------------------------------------------------------------- |
| Secrets        | Rotate on compromise; never commit `.env`.                        |
| Admin password | Change default immediately in prod.                               |
| TLS            | Enforce HTTPS (HSTS) at Nginx.                                    |
| CSRF           | Flask-WTF active for form POSTs. Exempt JSON login endpoint only. |
| Sessions       | Secure, HttpOnly, SameSite=Lax.                                   |
| Service worker | Review caching scope, avoid sensitive responses.                  |
| Rate limiting  | Tune per traffic profile.                                         |

## 15. Observability Suggestions (Future)

- Add structured JSON logging (request id, user id, latency).
- Integrate Sentry (DSN in `.env`).
- Add /metrics for Prometheus.

## 16. Common Issues

| Symptom          | Fix                                                            |
| ---------------- | -------------------------------------------------------------- |
| 400 CSRF         | Ensure `<input name="csrf_token" ...>` present in POST form.   |
| Auto admin login | Clear cookies or rotate `HELPCHAIN_SECRET_KEY`.                |
| Locale wrong     | Clear language cookie, test with IP header OR Accept-Language. |
| Stale homepage   | Hard refresh + unregister service worker.                      |

## 17. Minimal systemd Unit Example

```
[Unit]
Description=HelpChain Backend
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/helpchain/backend
Environment="HELPCHAIN_SECRET_KEY=/run/secrets/helpchain_secret"
ExecStart=/opt/helpchain/backend/.venv/bin/gunicorn -w 4 -b 127.0.0.1:8000 app:app
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

## 18. Secret Generation

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))" >> generated_secrets.txt
```

Keep `generated_secrets.txt` out of version control.

---

**Deployment complete ✔** – Proceed to smoke test `/api/login` and `/api/_health`.
