# TODO - HelpChain.bg (актуално)

Дата: 10 ноември 2025 г.

Това е текущият списък със задачи и статуси, поддържан при локалните тестове и разработки.

- [x] UI polish
  - Цел: премахване на inline стила и използване на `d-inline` в `admin_volunteers` формата.
  - Статус: completed

- [x] admin_volunteers flow стабилен
  - Цел: поправки в шаблона `backend/templates/admin_volunteers.html`, премахване на зависимост от `max`/`min` в Jinja и подсигуряване на пагинацията.
  - Статус: completed

- [x] Run full pytest suite
  - Цел: стартиране на пълното тестово изпълнение с file-backed SQLite DB (HELPCHAIN_TEST_DB_PATH) и валидация, че няма регресии.
  - Резултат: 131 passed, 1 skipped, 6 warnings (локално).
  - Статус: completed

- [x] Remove temporary Jinja globals (max/min)
  - Цел: премахнати временните `app.jinja_env.globals['max']` и `['min']` от `backend/appy.py` след като шаблоните са харденирани.
  - Статус: completed

- [x] Harden `strptime` Jinja filter
  - Цел: направен `strptime` филтър в `backend/appy.py` тип-безопасен (приема и `datetime` обекти, обработва грешки).
  - Статус: completed

- [x ] Fix Alembic migration ordering bug
  - Цел: разследване и поправка на Alembic ревизия, която проверява таблица създадена в по-късна ревизия. Това блокира "migrations-first" workflow на чисти бази.
    Анализ на history + идентифициране на грешния order.

Корекция на down_revision / разделяне на проблемни миграции.

Добавяне на финален “repair” migration (по желание).

Локален run: alembic upgrade head + pytest.

- Статус: not-started

Допълнителни бележки:

- Тестовата стабилизация използва file-backed SQLite DB за локални runs; това е лесно и надеждно локално решение, но за production/CI с миграции препоръчваме да поправим реда на ревизиите.
- Ако искаш, мога да:
  - добавя unit тест за `strptime` филтъра;
  - започна анализ и patch за Alembic migration-ordering.

---

Направено от екипа по тестова стабилизация.
