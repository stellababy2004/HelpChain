# Админ Панел: Цялостна документация (HelpChain)

## 1) Предназначение
Админ панелът служи за:

- оперативно управление на заявки (`requests`)
- управление на приоритет/статус/асайнване
- наблюдение на риск и SLA
- security наблюдение (auth опити, denied действия, anomaly индикатори)
- audit trail (кой, какво, кога, от къде)
- role governance за админ потребители

Основна имплементация: `admin.py`  
Модели: `models.py`  
Основен runbook: `admin-access.md`

## 2) Достъп и вход
Каноничен login:

- `GET/POST /admin/login` (primary)

Втори login endpoint:

- `GET/POST /admin/ops/login` (secondary/ops flow)

Logout:

- `GET/POST /admin/logout`

MFA/2FA endpoint-и:

- `/admin/mfa/setup`
- `/admin/mfa/verify`
- `/admin/mfa/backup-codes`
- `/admin/2fa`
- `/admin/email_2fa`
- `/admin/2fa/setup`
- `/admin/2fa/disable`

## 3) Админ роли и права
Поддържани роли:

- `superadmin`
- `ops`
- `readonly`

Role management:

- `GET /admin/roles`
- `POST /admin/roles/<admin_id>/role`

### Матрица на права (MVP)
- `readonly`: read-only екрани (`/admin/requests`, `/admin/audit`, `/admin/security`, dashboard/risk/sla)
- `ops`: всички readonly + оперативни действия (`status`, `assign/unassign`, `approve/reject interest`)
- `superadmin`: всички `ops` + високорискови действия (`archive`, `unlock`, `roles management`)

Защита:

- суперважни route-и са защитени с role allowlist
- last superadmin downgrade е блокиран

## 4) Основни секции в панела
### Dashboard/Overview
- `/admin/`
- `/admin/dashboard`
- KPI и бързи навигации

### Requests (оперативно ядро)
- `GET /admin/requests`
- `GET /admin/requests/<req_id>`
- `POST /admin/requests/<req_id>/status`
- `POST /admin/requests/<req_id>/assign`
- `POST /admin/requests/<req_id>/unassign`
- `POST /admin/requests/<req_id>/archive`
- `POST /admin/requests/<req_id>/unlock`
- notes/status history endpoints за заявка

Exports:

- `/admin/requests/export.csv`
- `/admin/requests/export.xlsx`
- anonymized варианти

### Risk/SLA
- `GET /admin/risk`
- `GET /admin/sla`

API KPI:

- `/admin/api/risk-kpis`
- `/admin/api/ops-kpis`

### Audit Trail
- `GET /admin/audit`
- филтри: `action`, `admin`, `request id`, период
- записите включват target, diff/payload, IP

Важно:

- за `security.denied_action` няма `view` линк към request detail (за да не води към synthetic/non-existing IDs)

### Security Overview
- `GET /admin/security`

KPI:

- successful logins (24h)
- failed logins (24h)
- lockout buckets (24h)
- risky actions (24h)
- denied actions (24h)

anomaly badges:

- failed-login spike
- repeated fails by IP
- repeated fails by username
- denied spike
- repeated denied

таблици:

- top failed-login IPs/usernames
- top denied-action IPs/usernames
- recent login attempts
- recent risky actions

### Professional leads / pro access
- `/admin/professional-leads`
- `/admin/pro-access` + review/approve/reject flows

### Volunteers
- `/admin/volunteers` и legacy `admin_volunteers` routes
- add/edit/delete/export

## 5) Security контроли (вече внедрени)
### 5.1 Brute-force защита
- DB-backed login attempts (`admin_login_attempts`)
- lockout логика с `429 + Retry-After` при threshold

### 5.2 Idle session timeout
- admin session timeout (20 мин неактивност)
- auto-logout при expiry

### 5.3 Immutable audit
- `admin_audit_events` е append-only:
- ORM guard (блокира update/delete)
- DB trigger (Postgres) за допълнителна защита

### 5.4 Denied action logging
- denied state-changing опити логват `security.denied_action`
- само за `POST/PUT/PATCH/DELETE` (без шум от `GET 403`)

## 6) Ключови модели (данни)
### AdminUser
- `username`, `email`, `password_hash`, `role`, MFA полета

### AdminLoginAttempt
- `created_at`, `username`, `ip`, `success`, `user_agent`

### AdminAuditEvent
- `created_at`
- `admin_user_id/admin_username`
- `action`
- `target_type/target_id`
- `ip`, `user_agent`
- `payload` (`old/new/meta`)

## 7) Оперативен runbook
### 7.1 Ако login не минава
- провери URL: трябва да е `/admin/login` (без точка в края)
- ако има lockout изчакай `Retry-After` или изчисти attempts в dev
- reset admin през `ensure_admin.py` с `ADMIN_SEED_FORCE_RESET=1`

### 7.2 Ако admin route връща 500
- първо проверка на логовете
- често: липсваща test/dev таблица `structures` или migration drift

### 7.3 Ако route дава 403
- провери role на user-а
- провери endpoint policy (superadmin-only за `archive`/`unlock`/`roles`)

### 7.4 Ако `view` от audit води до 404
- за `security.denied_action` това вече е коригирано и линк не се показва
- за други action-и 404 значи target записът реално липсва

## 8) Локални админ акаунти (текущо състояние)
Създадени са:

- `admin` (superadmin)
- `ops`
- `readonly`

Пароли за локалната среда са конфигурирани от `ensure_admin.py` по текущата сесия.

## 9) Smoke тестове (2-3 мин)
1. `GET /health` => `200`
2. Login като `admin` в `/admin/login` => redirect към admin зона
3. `/admin/security` => `200` и видими KPI/cards/tables
4. `/admin/audit` => `200`, филтър по action работи
5. Login като `ops`:
`POST archive/unlock` => `403 + security.denied_action` запис
6. Login като `readonly`:
`POST state-changing` => `403 + denied` запис
7. `/admin/security` отразява denied counters и топ таблици

## 10) Файлове за поддръжка
- `admin.py`
- `models.py`
- admin audit template
- admin security template
- `ensure_admin.py`
- `admin-access.md`
