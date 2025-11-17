# HelpChain – План за сигурност и хардening

Този файл описва всички текущи и планирани задачи по сигурността. Ще работим "лека по лека" – при приключване на задача ще я маркираме като Завършена и ще обновяваме този файл при нужда.

Легенда статус:

- ✅ Завършена
- 🔄 В процес
- ⏳ Предстои
- 🧪 За обсъждане / опционално

## 1. Основни текущи задачи

| ID  | Задача                      | Статус | Кратко описание                                                                                                               | Критерий за приемане                                                      |
| --- | --------------------------- | ------ | ----------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| 8   | Пълен CSRF за админ форми   | ✅     | Добавен `csrf_token` във всички POST форми (login, роли, 2FA setup/verify/disable, volunteers действия) + custom 400 страница | Ръчен тест без токен → 400 `csrf_error.html`; валидни форми приемат       |
| 9   | Argon2id миграция пароли    | 🔄     | Смяна PBKDF2 → Argon2id (64MB, t=3, p=2, hash_len=32) + автоматичен rehash при legacy login                                   | Нови хешове започват с `argon2id`; legacy хеш → rehash след успешен login |
| 10  | Audit лог за backup код     | ✅     | Логване action `backup_code_used` + fingerprint в `AuditLog`                                                                  | Запис при всяка успешна употреба; няма чувствителни данни                 |
| 11  | Failed login lockout        | ✅     | Блокиране след N (напр. 5) грешни опита за admin + временно заключване                                                        | След 5 грешки → отказ до изтичане на `locked_until`                       |
| 12  | Унифицирана политика пароли | ✅     | ≥10 символа, главна, малка, цифра – единичен валидатор за User/AdminUser                                                      | Опит за слаба парола → ValueError; силна парола приема                    |

## 2. Завършени мерки

| Задача                                                    | Статус | Какво е направено                                       |
| --------------------------------------------------------- | ------ | ------------------------------------------------------- |
| Rate limiting `/api/*` (без health)                       | ✅     | Sliding window IP → лимит headers                       |
| Secure cookies (Secure, HttpOnly, SameSite=Lax, lifetime) | ✅     | Настроени в `app.config`                                |
| JWT твърди claims (iss, aud, exp)                         | ✅     | Строг decode + fallback legacy                          |
| 2FA backup codes hashing (salt+pepper+sha256)             | ✅     | Файл `backup_codes.py`, masked display, one-time reveal |
| Pepper променлива среда                                   | ✅     | `HELPCHAIN_2FA_PEPPER` зададена, не се commit-ва        |
| Първоначална CSRF интеграция (публични форми)             | ✅     | `Flask-WTF` + токени в публични форми                   |

## 3. Допълнителни планирани подобрения (опционални / след основните)

| Име                                    | Тип | Описание                                                                                                     | Статус     |
| -------------------------------------- | --- | ------------------------------------------------------------------------------------------------------------ | ---------- |
| Security headers пакет                 | ✅  | Добавени CSP (Report-Only), X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy     | Завършено  |
| Парола ротация / `password_changed_at` | 🧪  | Поле за последна смяна и политика за периодично обновяване                                                   | Опционално |
| Blacklist често срещани пароли         | ✅  | Списък (top 10k) – отказ при съвпадение                                                                      | Завършено  |
| Monitoring & Alerts                    | 🧪  | Sentry + логване на rate-limit удари                                                                         | Опционално |
| Refresh token / ротация JWT            | 🧪  | Кратки access + дълги refresh → намаляване на риск от кражба                                                 | Опционално |
| Vulnerability scanning CI              | ✅  | Dependabot + pip-audit SARIF + устойчив safety JSON (`scan --json` + fallback) + HTTP stack upgrade завършен | Завършено  |
| Security README / публична политика    | 🧪  | Кратък документ за потребителите как защитаваме данните                                                      | Опционално |

## 4. Детайлни acceptance критерии (референция)

### 13. Common password blacklist

### 14. Vulnerability scanning CI

- Workflow: `.github/workflows/security-audit.yml` (pull_request, push, schedule daily 03:00 UTC, manual dispatch).
- Инструменти: `pip-audit` (SARIF → Code Scanning), `safety` (JSON артефакт).
- Dependabot: `.github/dependabot.yml` (pip + github-actions weekly).
- Локален скрипт: `scripts/run_security_audit.py` – инсталира инструменти при нужда и генерира `pip_audit_results.txt` + `safety_results.json`.
- Acceptance: workflow стартира успешно на PR; SARIF качен; находките прегледани преди merge.

Първи локален резултат (2025-11-15):

```
pip-audit findings (извадка):
Name            Version ID                  Fix Versions
h11             0.14.0  GHSA-vqfr-h8mv-ghfj 0.16.0
jinja2          3.1.2   GHSA-h5c8-rqwp-cp95 3.1.3
jinja2          3.1.2   GHSA-h75v-3vvj-5mfj 3.1.4
jinja2          3.1.2   GHSA-q2x7-8rv6-6q7h 3.1.5
jinja2          3.1.2   GHSA-gmj6-6f8f-6699 3.1.5
jinja2          3.1.2   GHSA-cpwx-vrp4-4pq7 3.1.6
python-socketio 5.8.0   GHSA-g8c6-8fjj-2r4m 5.14.0
```

Следващи стъпки:

1. Завършен upgrade: jinja2→3.1.6, python-socketio→5.14.0 (премахва съответните находки).
2. Отложен upgrade: h11 (останало 0.14.0) заради constraint `httpcore 0.17.3` (изисква h11<0.15). Необходима е координирана актуализация към по-нови верси httpcore/httpx.
3. Добавен workflow конвертор на safety JSON → SARIF (`scripts/convert_safety_to_sarif.py`).
4. След завършване на httpx/httpcore upgrade → очаква се да отпадне GHSA-vqfr-h8mv-ghfj.

- Файл: `security/common_passwords_top10k.txt` (първоначален subset ~500; лесно заменим с пълен списък).
- Lazy load в `models.py` чрез `_load_common_passwords()` → сет (lowercase).
- Проверка в `validate_password_strength` след всички други правила; ако `password.lower()` е в blacklist → `ValueError("Паролата е твърде често използвана и не е позволена")`.
- Fail-open само при проблем с четенето на файла (липсващ файл) – не потиска ValueError.
- Smoke тест: `Password123` (продава всички сложностни правила) е отхвърлена с общото съобщение; силна уникална `UncommonStr0ngX123` се приема.

Резултат от smoke тест (2025-11-15):

```
[OK] Rejected common password 'Password123': Паролата е твърде често използвана и не е позволена
[OK] Strong password accepted: UncommonStr0ngX123
```

Допълнителни проверки: кратки често срещани пароли (password, 123456, qwerty) се отхвърлят по правилата за дължина/сложност.

### Security headers

- Добавен `@app.after_request` middleware:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - `Permissions-Policy: camera=(), microphone=(), geolocation=()`
  - `Content-Security-Policy-Report-Only: default-src 'self'; img-src 'self' data:; script-src 'self'; style-src 'self' 'unsafe-inline'`
- Конфигурация:
  - `SECURITY_HEADERS` (default True)
  - `CSP_REPORT_ONLY` (default True)
  - `CSP_POLICY` (низ за политика)

### 8. Пълен CSRF за админ форми

- Всички `.html` админ темплейти с `<form method="POST">` имат скрит `<input name="csrf_token">`.
- AJAX POST добавя header `X-CSRFToken`.
- Тест: изтрит токен → 400 + `csrf_error.html`.

### 9. Argon2id миграция

- Инсталиран `argon2-cffi`.
- Модели: `set_password` генерира Argon2id (m≥48MB, t=3).
- `check_password` rehash при legacy формат.
- Legacy хешове постепенно изчезват.

### 10. Audit лог backup код

- При успешна verify → `AuditLog(action="backup_code_used", metadata_json={"code_hash_prefix": <първи 8 символа>})`.
- В `backup_codes.verify_and_consume(..., actor_user_id=User.id)` има опционален вътрешен audit запис; препоръчително е и на място на употреба (контролер) да се прави явен запис.
- Никога не се записва/plaintext код; само пръстов отпечатък (първите 8 символа от хеша).

Резултат от smoke тест (2025-11-15):

- Успешна верификация на backup код → записан `AuditLog` с `code_hash_prefix` (8 символа), `target_type=admin_user` и `target_id=<AdminUser.id>`; повторна употреба е неуспешна (False).
- Никакъв plaintext или пълна сол.

### 11. Failed login lockout

- Полета `failed_login_attempts`, `locked_until` използвани.
- След праг (5) → set `locked_until = now + timedelta(minutes=10)` (HTTP 423 при POST към `/admin/login`).
- Успешен login → reset брояча и `locked_until`.

Резултат от smoke тест (2025-11-15):

- 5 неуспешни опита → 401; шестият с вярна парола → 423 (заключен акаунт).
- Ръчно изтичане на `locked_until` → следващ успешен login връща 302 към `/admin_dashboard`.

### 12. Унифицирана политика пароли

- Един helper `validate_password_strength(password)`.
- Правила: ≥10, ≥1 lowercase, ≥1 uppercase, ≥1 digit.
- Админ и user използват един и същи метод.

## 5. Порядък на изпълнение (препоръчан)

1. CSRF admin форми (завършено).
2. Argon2id миграция (текущо – плавен upgrade).
3. Унифицирана политика пароли.
4. Lockout механизъм.
5. Audit лог за backup код.
6. Опционални подобрения.

## 6. Бележки за миграция Argon2id

- Текущи параметри в `models.py`: `time_cost=3`, `memory_cost=65536` (64MB), `parallelism=2`, `hash_len=32`.
- Първоначално планиран 48MB, директно избран 64MB след преценка за сигурност; наблюдение на latency предстои.
- Автоматичен rehash при успешен login на legacy PBKDF2 (prefix не започва с `argon2`).
- При бъдеща промяна на параметри библиотеката проверява `check_needs_rehash` и обновява.

### Резултати от проверка (2025-11-15)

- admin (legacy PBKDF2) → успешна верификация и миграция към Argon2id (`$argon2id$…`).
- `argon_test` → вече е с Argon2id.
- Силна парола `StrongPass123` → записва се като Argon2id.
- Слабите пароли са отхвърлени с очакваните съобщения:
  - `short8A1` → „Паролата трябва да бъде поне 10 символа“
  - `nouppercase123` → „Паролата трябва да съдържа поне една главна буква“
  - `NOLOWERCASE123` → „Паролата трябва да съдържа поне една малка буква“
  - `NoDigitsAAAA` → „Паролата трябва да съдържа поне една цифра“
  - `short` → „Паролата трябва да бъде поне 10 символа“

## 7. Команди за зависимости

```pwsh
pip install argon2-cffi
```

## 8. Актуализация на този файл

Редакция след приключване на всяка задача: статус → ✅ и добавяне на кратка бележка ако има промени извън първоначалния критерий.

---

Последна редакция: 2025-11-15 (добавен blacklist често срещани пароли)

## 9. HTTP Stack Upgrade (2025-11-15)

Първоначално BLOCKED (липса на версия позволяваща h11>=0.16.0). Мониторинг скрипт `scripts/monitor_http_stack_upgrade.py` (автоматизиран чрез workflow `monitor-http-stack-upgrade`) откри, че последната версия `httpx==0.28.1` позволява инсталация с `h11==0.16.0` без конфликт (httpcore автоматично обновен до `1.0.9`).

Извършени действия:

1. Добавени пинове в `requirements.in`: `httpx==0.28.1`, `h11==0.16.0`.
2. Регенирано `requirements.txt` (httpcore резолвнат до 1.0.9).
3. Стартиран `scripts/run_security_audit.py` → няма pip-audit findings (адвайзъри за h11 отпаднали).
4. Workflow за мониторинг остава активен за бъдещи регресии.

Резултат: GHSA-vqfr-h8mv-ghfj ремедиран. Статус: ✅ Завършено.

Бележка: Safety JSON парсингът е стабилизиран (използва `safety scan --json` + fallback към `check --json`; извличане на чист JSON блок от stdout). Конверторът `scripts/convert_safety_to_sarif.py` поддържа и двата ключа: `issues` и `vulnerabilities`, както и `meta` / `report_meta` за версия.

## 10. Safety Audit Output Stabilization (2025-11-15)

Проблем: Старият `safety check --json` добавя банер/декориран текст преди/след JSON, причинявайки `JSONDecodeError`.
Решение:

1. Смяна основна команда → `safety scan --json` (нова, чист JSON).
2. Fallback към `check --json` при липса на новата команда.
3. Робустен екстрактор: намира първата `{` и последната `}` и опитва повторно `json.loads`.
4. Конвертор адаптиран: приема схеми с `issues` (стар) или `vulnerabilities` (нов), чете версия от `meta.safety_version` или `report_meta.safety_version`.
5. Локален скрипт `run_security_audit.py` обновен – логика за парсинг + запис на необработен stdout за трасировка.

Резултат: Няма parse error; SARIF артефакт се генерира последователно; бъдещи промени в safety CLI намаляват риска от счупване.

### 11. CLI флагове за audit скрипта (2025-11-15)

Добавени аргументи в `scripts/run_security_audit.py` за по-ясно и контролируемо поведение:

```
--no-safety          Пропуска safety сканирането
--safety-timeout N   Timeout (секунди) за safety процеса (default 30)
--safety-mode MODE   'scan' | 'check' | 'auto' (auto: опитва scan после fallback check)
```

ENV override: `SAFETY_SKIP=1` (авариен глобален skip – ако е зададен, флаговете се игнорират).
Поведение при timeout: процесът се kill-ва и ако има fallback (auto) се пробва следващия вариант.
Бъдещо разширение: `--json-summary` за машинно четим агрегат, dashboard интеграция.
