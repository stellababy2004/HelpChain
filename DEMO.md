# DEMO — кратко ръководство за HelpChain.bg

Това е кратко демо и инструкции за локално стартиране на проекта.

Какво представлява:

- HelpChain е Flask приложение за свързване на нуждаещи се с доброволци.
- Кодът съдържа backend в папката `backend` и различни помощни скриптове.

Бърз старт (локално):

1. Създайте виртуална среда и я активирайте:

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate
```

2. Инсталирайте зависимостите:

```bash
pip install -r requirements.txt
```

3. Настройте основни environment променливи (пример):

```bash
set HELPCHAIN_SECRET_KEY=change-me-please       # Windows (PowerShell)
export HELPCHAIN_SECRET_KEY=change-me-please    # macOS / Linux
```

4. Стартирайте приложението за разработка:

```bash
python run.py
# или (ако предпочитате Flask):
export FLASK_APP=backend.app
flask run
```

5. Тествайте (опционално):

```bash
pytest -q
```

Бележки:

- За production разгръщане се използват специфични команди (пример: `uvicorn`/`gunicorn`) и допълнителни конфигурации.
- Вижте `VERCEL_DEPLOYMENT.md` за бележки относно Vercel и `runtime.txt`.

Ако желаете, мога да добавя примерни `.env` шаблони или да подготвя Docker/Procfile за по-лесно разгръщане.
