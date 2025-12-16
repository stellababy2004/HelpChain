# Vercel SAML SSO с Okta (безплатно)

Този playbook описва точните стъпки „къде да кликнеш“ за бърза интеграция SAML (Okta Developer) към Vercel Team, включително тест/rollback.

## Предпоставки
- Okta Developer акаунт: https://developer.okta.com/signup/
- Достъп до Vercel Team Settings → Security
- Двама администратори за тест на SSO и fallback акаунт с 2FA

## 1) Вземи SAML данните от Vercel
1. Vercel → Team Settings → Security → SAML → Configure.
2. Копирай:
   - ACS URL (Assertion Consumer Service)
   - Entity ID (Audience URI)
3. Остави страницата отворена – ще се върнем да качим IdP metadata и да натиснем Save.

## 2) Създай SAML приложение в Okta
1. Okta Admin → Applications → Create App Integration.
2. Sign-in method: SAML 2.0 → Next.
3. App name: `HelpChain Vercel SSO` → Next.
4. Basic SAML Settings:
   - Single sign on URL: постави ACS URL от Vercel (✓ Use this for Recipient URL and Destination URL).
   - Audience URI (SP Entity ID): постави Entity ID от Vercel.
   - Name ID format: `EmailAddress`; Application username: `Email`.
5. Attribute Statements:
   - Name: `email` → Value: `user.email`
   - Name: `name`  → Value: `user.displayName` (или `user.firstName` + `user.lastName`)
   - Optional: `groups` → Matches regex `.*`
6. Finish → Assignments → Assign to Groups/People → избери администраторите и/или група `HelpChain`.

## 3) Свържи Okta с Vercel
1. Okta → Application → Sign On → "Metadata Details" → копирай **Metadata URL** или свали XML.
2. Върни се във Vercel → SAML → Upload/URL на IdP metadata → Save.
3. Натисни "Test SAML login" и влез с Okta акаунт.
4. След като ДВАМА админи потвърдят успешен вход → включи "Require SAML to access this Team".

## 4) 2FA Enforcement и Preview защита
- Vercel → Team Settings → Security → Two‑Factor Authentication Enforcement → Enable.
- Project → Settings → Deployment Protection → Preview → Enable.
- За smoke на PR previews ползвай “Enable bypass link”.

## 5) Валидация
- Успешен SAML вход за 2+ админи.
- Няма достъп без SAML (след "Require SAML").
- 2FA статус: Team Members показва "2FA enabled" за всички ключови акаунти.
- Smoke: основни маршрути връщат 200 със bypass линк.

## 6) Rollback (ако нещо се счупи)
- Изключи "Require SAML" в Vercel (Security → SAML).
- Увери се, че имаш Break‑glass админ акаунт с 2FA (локален Vercel, не само Okta).
- Коригирай атрибути/NameID в Okta и повтори теста.

## Бележки
- SCIM (Directory Sync) в Okta е платен. За безплатен старт използвай SAML + 2FA enforcement и ръчно управление на членове.
- По‑късно можеш да мигрираш към SCIM (Okta/Azure P1) или self‑hosted Keycloak.
