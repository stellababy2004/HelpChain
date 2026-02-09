# HelpChain Production Email Setup Guide

Това ръководство обяснява как да настроите имейл нотификациите за production среда.

## Поддържани SMTP доставчици

### 1. SendGrid (Препоръчително)

- **Регистрация**: https://sendgrid.com
- **Безплатен план**: 100 имейла/ден
- **Настройки**:
  ```
  MAIL_SERVER=smtp.sendgrid.net
  MAIL_PORT=587
  MAIL_USE_TLS=True
  MAIL_USE_SSL=False
  MAIL_USERNAME=apikey
  MAIL_PASSWORD=YOUR_SENDGRID_API_KEY
  MAIL_DEFAULT_SENDER=contact@helpchain.live
  ```

### 2. Gmail с App Password

- **Изисквания**: Gmail акаунт с 2FA активиран
- **Генериране на App Password**: https://myaccount.google.com/apppasswords
- **Настройки**:
  ```
  MAIL_SERVER=smtp.gmail.com
  MAIL_PORT=587
  MAIL_USE_TLS=True
  MAIL_USE_SSL=False
  MAIL_USERNAME=your-gmail@gmail.com
  MAIL_PASSWORD=YOUR_APP_PASSWORD
  MAIL_DEFAULT_SENDER=contact@helpchain.live
  ```

### 3. Zoho Mail (Професионално решение) ✅ АКТИВНО

- **Регистрация**: https://www.zoho.com/mail/
- **Цена**: Безплатен план до 5GB, платени планове от $1/месец
- **Текущи настройки** (работещи):
  ```
  MAIL_SERVER=smtp.zoho.eu
  MAIL_PORT=587
  MAIL_USE_TLS=True
  MAIL_USE_SSL=False
  MAIL_USERNAME=contact@helpchain.live
  MAIL_PASSWORD=YOUR_ZOHO_APP_PASSWORD
  MAIL_DEFAULT_SENDER=contact@helpchain.live
  ```
- **Алтернативни настройки (SSL)**:
  ```
  MAIL_SERVER=smtp.zoho.eu
  MAIL_PORT=465
  MAIL_USE_TLS=False
  MAIL_USE_SSL=True
  MAIL_USERNAME=contact@helpchain.live
  MAIL_PASSWORD=YOUR_ZOHO_APP_PASSWORD
  MAIL_DEFAULT_SENDER=contact@helpchain.live
  ```

**Важно за Zoho:**

- Използвайте пълния имейл адрес като username
- За 2FA акаунти използвайте App Password (генерира се в Settings → Security → App Passwords)
- Текущата конфигурация използва App Password за 2FA

### 4. Mailgun

- **Регистрация**: https://www.mailgun.com
- **Безплатен план**: 5,000 имейла/месец
- **Настройки**:
  ```
  MAIL_SERVER=smtp.mailgun.org
  MAIL_PORT=587
  MAIL_USE_TLS=True
  MAIL_USE_SSL=False
  MAIL_USERNAME=YOUR_MAILGUN_SMTP_USERNAME
  MAIL_PASSWORD=YOUR_MAILGUN_SMTP_PASSWORD
  MAIL_DEFAULT_SENDER=contact@helpchain.live
  ```

## Стъпки за настройка

1. **Изберете доставчик** и се регистрирайте
2. **Генерирайте credentials** (API key, app password, etc.)
3. **Обновете .env файла** с правилните настройки
4. **Тествайте** с `python test_email.py`
5. **Deploy** приложението

## Development среда

За development използвайте Mailtrap:

```
MAIL_SERVER=smtp.mailtrap.io
MAIL_PORT=2525
MAIL_USE_TLS=True
MAIL_USE_SSL=False
MAIL_USERNAME=YOUR_MAILTRAP_USERNAME
MAIL_PASSWORD=YOUR_MAILTRAP_PASSWORD
MAIL_DEFAULT_SENDER=contact@helpchain.live
```

## Troubleshooting

- **Authentication Failed**: Проверете credentials
- **Connection Timeout**: Проверете firewall и интернет връзка
- **TLS/SSL Errors**: Проверете MAIL_USE_TLS и MAIL_USE_SSL настройките
- **Rate Limits**: Проверете лимитите на доставчика

## Fallback механизъм

Ако SMTP изпращането не успее, имейлите се записват в `sent_emails.txt` файл за ръчна обработка.
