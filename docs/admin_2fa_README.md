# Admin 2FA (TOTP) — Конфигурация и поведение

Кратко ръководство за администрацията и разработчиците относно имплементацията на двуфакторна автентикация (TOTP) в HelpChain.

Основни endpoints и flow

- `GET /admin/login` — показва формата за логин (username + password).
- `POST /admin/login` — обработва логин. Поведение:
  - Ако `EMAIL_2FA_ENABLED` е активирано — преминава към email 2FA flow (`/admin/email_2fa`).
  - Иначе, ако потребителят има `two_factor_enabled == True`, сървърът сетва `session['pending_admin_id']` и редиректва към `/admin/2fa` (TOTP verification).
  - Ако няма 2FA — извършва стандартен `login_user(admin_user)` и редирект към админ таблото.
- `GET|POST /admin/2fa` — страница за въвеждане на TOTP кода. Очаква налична сесия `pending_admin_id` (поддържа и legacy `pending_admin_user_id` за backward compatibility). След успешна верификация изпълнява `login_user()` и изчиства и двата ключа от сесията.
- `GET|POST /admin/2fa/setup` — UI за настройка на TOTP (QR/provisioning uri). При успешна верификация записва `two_factor_secret` и `two_factor_enabled` в базата (`db.session.commit()` се извиква).
- `POST /admin/2fa/disable` — деактивира TOTP и персистира промяната в DB.

Ключови модели/атрибути

- `AdminUser.two_factor_enabled` (Boolean) — дали TOTP е активиран.
- `AdminUser.two_factor_secret` (String) — базов32 секретът за TOTP (provisioning URI генерира QR код).
- Model helpers: `enable_2fa()`, `disable_2fa()`, `verify_totp(token)`, `get_totp_uri()` — вече налични.

Deprecated / legacy session key

- Нов (унифициран) ключ в сесията: `pending_admin_id` (integer).
- Legacy ключ, използван в някои по-стари shim-ове: `pending_admin_user_id`.
- Съвет: използвайте и проверявайте само `pending_admin_id`. Шим-овете в кода остават да четат legacy ключа само за съвместимост, но при нови интеграции/fixture-и трябва да се задава `pending_admin_id`.

Security и operational notes

- Recovery codes: настоящата минимална имплементация не генерира recovery codes. Препоръчваме да добавите backup/recovery кодове (еднократни) за админи, записани криптирано в DB или изнесени в секретен мениджър.
- Secrets management: не съхранявайте production секрети в plaintext `.env` в repo. Препоръчваме GitHub Secrets/HashiCorp Vault/Azure KeyVault за production; за краткосрочно решение — `git-crypt`/`sops` за шифровани файлове.
- Тестове: съществуват pytest fixtures (`test_admin_user`, `init_test_data`) и тестове за email-2fa. Допълнителни тестове за TOTP flow са добавени в `tests/test_admin_2fa.py`.

Developer checklist (горещи поправки, вече приложени)

- Уеднаквяване на session key: `pending_admin_id` (поддържа legacy ключ). — Applied
- `db.session.commit()` след `enable_2fa()` и `disable_2fa()` в админ роутовете. — Applied
- Login flow: при `two_factor_enabled==True` редирект към `/admin/2fa`. — Applied

How to test locally

1. Стартирайте тестовата среда (pytest). Пример: 

```powershell
conda activate helpchain
pytest tests/test_admin_2fa.py -q
```

2. Ръчен тест:
  - Създайте админ потребител, активирайте 2FA (`admin.enable_2fa()`), запазете (commit), след това POST към `/admin/login` и очаквайте redirect към `/admin/2fa`.

Notes for deployment

- Уверете се, че всички промени са тествани в staging преди merge в `main` и production deploy.
- Ако използвате CI, добавете проверки, че `pyotp` е инсталиран и тестовете за 2FA минават в CI pipeline.

Contact

За въпроси относно 2FA flow — ping в PR или open an issue в репото.
