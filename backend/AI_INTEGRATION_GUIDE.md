# 🤖 AI Chatbot Integration - Ръководство за администратори

## 📋 Обзор

HelpChain чатботът сега има интегрирана AI функционалност с поддръжка на:
- **OpenAI GPT** (gpt-3.5-turbo, gpt-4)
- **Google Gemini** (gemini-pro)

## 🔧 Настройка на AI API ключове

### OpenAI настройка:
1. Получете API ключ от [OpenAI Platform](https://platform.openai.com/api-keys)
2. Добавете в `.env` файла:
```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-3.5-turbo
OPENAI_MAX_TOKENS=150
OPENAI_TEMPERATURE=0.7
```

За персистентност (препоръчано за локални развойни инстанции), можете да копирате примерния конфигурационен файл в папката `instance` и да добавите ключовете там:

```powershell
# от корена на проекта (backend)
Copy-Item instance\config.py.example instance\config.py
# Редактирайте instance\config.py и добавете вашите ключове
```

Приложението зарежда конфигурацията чрез `os.environ` (ако използвате променливи на средата) или директно от `instance/config.py` ако добавите променливи там.

### Google Gemini настройка:
1. Получете API ключ от [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Добавете в `.env` файла:
```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-pro
GEMINI_MAX_TOKENS=150
GEMINI_TEMPERATURE=0.7
```

Или използвайте `instance\config.py` (копирайте примера както е показано по-горе) за по-персистентна конфигурация.

## 🎯 Как работи AI системата

### Интелигентен отговор в 4 стъпки:
1. **FAQ проверка** - Търси високо съвпадение с готовите отговори
2. **AI генерация** - Използва AI за персонализирани отговори
3. **FAQ предложения** - Показва близки FAQ при ниска увереност
4. **Fallback** - Общ отговор при липса на съвпадение

### AI контекст:
- Запомня последните 3 съобщения в разговора
- Автоматично разпознава езика на въпроса
- Винаги отговаря на български език
- Специализиран за HelpChain услуги

## 📊 AI Администрация

### Dashboard: `/admin/ai`
- **AI Status** - Статус на активните AI провайдери
- **Analytics** - Статистики за AI отговори
- **Configuration** - Настройки и тестване
- **Performance** - Време за отговор и tokens

### API Endpoints:
- `GET /api/ai/status` - AI статус
- `GET /api/ai/test` - Тест на връзките
- `POST /api/ai/demo` - Demo тест
- `GET /api/chatbot/analytics` - Подробна аналитика

## 🔍 Мониторинг и аналитика

### Проследявани метрики:
- **AI Confidence** - Увереност в отговора (0-1)
- **Processing Time** - Време за генериране
- **Token Usage** - Използвани API tokens
- **Language Detection** - Разпознат език
- **Provider Used** - Кой AI модел е използван

### Performance индикатори:
- Средна увереност > 0.7 = добро качество
- Време за отговор < 2s = добра производителност
- FAQ hit rate > 60% = ефективна база знания

## ⚡ Оптимизация

### За по-добри AI отговори:
1. **Обогатяване на FAQ** - Добавяйте повече ключови думи
2. **Контекстуални данни** - AI използва историята на разговора
3. **Confidence threshold** - Настройвайте праг за AI активация
4. **Model selection** - OpenAI за сложни въпроси, Gemini за скорост

### Cost management:
- Мониторирайте token usage в dashboard
- Използвайте gpt-3.5-turbo за по-ниски разходи
- Настройте max_tokens за контрол на дължината

## 🛠️ Troubleshooting

### Чести проблеми:

**AI не се активира:**
- Проверете API ключовете в `.env`
- Тествайте връзката в `/admin/ai`
- Проверете логовете за грешки

**Ниско качество на отговорите:**
- Прегледайте system prompt в `ai_config.py`
- Добавете повече FAQ примери
- Настройте temperature параметъра

**Бавни отговори:**
- Намалете max_tokens
- Използвайте по-бърз модел
- Проверете мрежовата връзка

## 📈 Следващи подобрения

### Планирани функции:
- **Multilingual support** - Автоматичен превод
- **Learning system** - Подобряване базирано на feedback
- **Advanced analytics** - ML insights за потребителското поведение
- **Custom training** - Fine-tuning с HelpChain данни

## 🔒 Сигурност и Privacy

### Важни бележки:
- AI провайдерите получават съобщенията за обработка
- Не изпращайте лична информация в тестовете
- Логовете се съхраняват локално в базата данни
- API ключовете трябва да се пазят в тайна

---

## 🧪 Development helpers (mock, sanitization и тестове)

### Sanitization & extraction на OpenAI ключа

Проектът автоматично почиства и валидира стойността на `OPENAI_API_KEY` преди да я използва.
Основни мерки:
- Нормализация (NFKC) и trim()
- Премахване на невидими/control символи (zero-width, BOM и т.н.)
- Проверка за ASCII-only
- Детекция за очевидни placeholders (напр. 'your', 'ваш', 'replace')
- Ако стойността изглежда като плейсхолдър, diagnostic ще сигнализира и няма да се правят заявки към OpenAI.

Допълнителна автоматична екстракция:
- Ако стойността съдържа смес от текст и възможен ключ, проектът опитва да извлече първия ASCII-looking substring от вида `sk-[A-Za-z0-9_-]{20,100}` и да го използва за кратки health checks. Това е защитна мярка, а не заместител на реалния чист ключ.

### Mock режим за разработка (`AI_DEV_MOCK`)

За удобство при разработка можеш да включиш mock режим, който симулира успешно поведение на доставчиците, без да се изисква валиден API ключ.

Пример (PowerShell, само за текущата сесия):
```powershell
$env:AI_DEV_MOCK = '1'
& '.venv\Scripts\python.exe' 'scripts/test_ai.py'
```

В mock режим:
- `ai_service.test_connection()` връща `status: ok` за всички доставчици
- `ai_service.generate_response()` връща кратък canned отговор `{ 'response': 'Това е mock отговор...' }`

Mock режимът трябва да се използва само за локална разработка и тестове. Не го включвай в production.

### `scripts/test_ai.py`

Файлът `scripts/test_ai.py` е диагностичен скрипт, който:
- Показва дали `OPENAI_API_KEY` и други променливи са зададени
- Извиква `ai_service.test_connection()` за кратък health check
- Връща ясни съобщения при placeholder, non-ASCII проблеми или при липса на ключ

Как да го използваш:
1. За бърз health check (ако имаш ключ):
```powershell
$env:OPENAI_API_KEY = 'sk-REPLACE_WITH_REAL_KEY'
& '.venv\Scripts\python.exe' 'scripts/test_ai.py'
```

2. Ако нямаш ключ и искаш да разработваш локално:
```powershell
$env:AI_DEV_MOCK = '1'
& '.venv\Scripts\python.exe' 'scripts/test_ai.py'
```

### Препоръки и добри практики
- Дръж ключовете извън версията (не ги комитвай)
- Използвай отделен dev ключ/проект за локална разработка
- Ако ключът е компрометиран — ревокирай и създай нов в OpenAI dashboard
- Добави мониторинг/аларми за необичаен usage


**За техническа поддръжка:** contact@helpchain.live  
**Документация:** [HelpChain Admin Guide](mailto:admin@helpchain.bg)