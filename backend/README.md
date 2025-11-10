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
- Утвърдихме конфигурацията – `.env.example` и `config.py` вече описват Postgres setup, а уеб push модулът показва ясни fallback-и при липсващ VAPID ключ.
- Утвърдихме конфигурацията – `.env.example` и `config.py` вече описват Postgres setup, а уеб push модулът показва ясни fallback-и при липсващ VAPID ключ.

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
