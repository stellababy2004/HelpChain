# HelpChain (backend)

## Releases

### v0.1.0 — 2025-09-29

Initial test-stable release — 13 passing tests.

Highlights

- Тестовете са рефакторирани и стабилизирани (mocked HTTP за чатбот).
- Welcome email тестът е направен безопасен чрез mock на SMTP.
- Добавен conftest.py с фикстури и PYTHONPATH корекция за test пакетите.
- Добавен LICENSE (MIT) и tag `v0.1.0`.
- Pre-commit hooks (black, ruff и др.) вкарани в CI локално.
