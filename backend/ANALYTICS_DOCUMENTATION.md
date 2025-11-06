# 📊 HelpChain Analytics System Documentation

## Преглед

HelpChain Analytics System е модулна система за анализ на данни и статистики, която предоставя детайлни insights за работата на платформата за помощ. Системата е проектирана да осигури real-time данни, визуализации и инструменти за филтриране.

## 🏗️ Архитектура

### Основни Компоненти

1. **Analytics Engine** (`admin_analytics.py`)
2. **Web Routes** (`appy.py`)
3. **Frontend Dashboard** (`admin_analytics_dashboard.html`)
4. **Debug Tools** (`debug_analytics.py`)

## 📁 Файлова Структура

```
backend/
├── admin_analytics.py          # Основен analytics engine
├── appy.py                     # Flask routes за analytics
├── debug_analytics.py          # Debug и тестване
├── test_analytics_route.py     # Тестове за route логика
├── test_full_route.py          # Пълни route тестове
└── templates/
    └── admin_analytics_dashboard.html  # Frontend template
```

## 🔧 Основни Класове

### 1. AnalyticsEngine

Основният клас за изчисляване на статистики и анализ на данни.

#### Методи:

##### `get_dashboard_stats(days=30)`

Получава основни статистики за dashboard.

**Параметри:**

- `days` (int): Период за анализ в дни (по подразбиране 30)

**Връща:**

```python
{
    'totals': {
        'requests': int,           # Общо заявки
        'volunteers': int,         # Общо доброволци
        'users': int,              # Общо потребители
        'period_requests': int     # Заявки за периода
    },
    'status_stats': {              # Статистики по статуси
        'status_name': count, ...
    },
    'daily_stats': [               # Дневни статистики
        {
            'date': 'DD.MM',
            'requests': int,
            'volunteers': int
        }, ...
    ],
    'location_stats': {            # Статистики по локации
        'location': count, ...
    },
    'category_stats': {            # Статистики по категории
        'category': count, ...
    },
    'period_days': int
}
```

##### `get_daily_stats(days=30)`

Получава дневни статистики за графики.

##### `get_location_stats()`

Анализира заявки и доброволци по географски локации.

##### `get_category_stats()`

Категоризира заявки по тип въз основа на ключови думи:

- **здраве**: медицински услуги
- **документи**: административни услуги
- **социална помощ**: материална подкрепа
- **транспорт**: превозни услуги
- **образование**: образователни услуги
- **друго**: останали категории

##### `get_geo_data()`

Получава геолокационни данни за карта.

**Връща:**

```python
{
    'requests': [               # Заявки на картата
        {
            'id': int,
            'name': str,
            'title': str,
            'status': str,
            'lat': float,
            'lng': float,
            'type': 'request',
            'created_at': str
        }, ...
    ],
    'volunteers': [             # Доброволци на картата
        {
            'id': int,
            'name': str,
            'location': str,
            'lat': float,
            'lng': float,
            'type': 'volunteer'
        }, ...
    ],
    'centers': [                # Градски центрове
        {
            'city': str,
            'lat': float,
            'lng': float,
            'volunteer_count': int,
            'type': 'center'
        }, ...
    ]
}
```

##### `get_success_rate()`

Изчислява процент успешно завършени заявки.

### 2. RequestFilter

Клас за филтриране и търсене на заявки.

#### Методи:

##### `filter_requests(status, date_from, date_to, location, keyword, category, priority, page, per_page)`

Филтрира заявки според множество критерии.

**Параметри:**

- `status` (str): Статус на заявката
- `date_from` (datetime): Начална дата
- `date_to` (datetime): Крайна дата
- `location` (str): Локация
- `keyword` (str): Ключова дума за търсене
- `category` (str): Категория
- `priority` (str): Приоритет
- `page` (int): Номер на страница
- `per_page` (int): Записи на страница

**Връща:**

```python
{
    'items': [HelpRequest, ...],   # Списък с заявки
    'total': int,                  # Общо заявки
    'pages': int,                  # Общо страници
    'current_page': int,           # Текуща страница
    'has_prev': bool,              # Има предишна страница
    'has_next': bool,              # Има следваща страница
    'prev_num': int,               # Номер на предишна
    'next_num': int                # Номер на следваща
}
```

##### `get_filter_options()`

Получава налични опции за филтри.

### 3. RealtimeUpdates

Клас за real-time обновяване на данни.

#### Методи:

##### `get_recent_activity(limit=10)`

Получава последна активност в системата.

##### `get_live_stats()`

Получава статистики за live обновяване.

## 🌐 Web Routes

### `/admin/analytics`

Основен analytics dashboard endpoint.

**Метод:** GET
**Аутентификация:** Изисква admin login
**Параметри:**

- `page`: Номер на страница
- `per_page`: Записи на страница
- `status`: Филтър по статус
- `date_from`: Начална дата (YYYY-MM-DD)
- `date_to`: Крайна дата (YYYY-MM-DD)
- `location`: Филтър по локация
- `keyword`: Ключова дума за търсене
- `category`: Филтър по категория

**AJAX поддръжка:** Връща JSON при X-Requested-With: XMLHttpRequest

### `/admin/export`

Export на данни (планиран).

## 📱 Frontend Dashboard

### Функционалности

1. **KPI Cards**

   - Общо заявки
   - Активни заявки
   - Успешно завършени
   - Нови днес

2. **Графики**

   - Дневни статистики (Line Chart)
   - Статуси на заявки (Pie Chart)
   - Категории заявки (Bar Chart)

3. **Карта**

   - Географско разпределение на заявки
   - Локации на доброволци
   - Градски центрове

4. **Филтри и Търсене**

   - Филтър по статус
   - Филтър по дати
   - Филтър по локация
   - Текстово търсене

5. **Real-time Updates**
   - Автоматично обновяване на данни
   - Последна активност
   - Live статистики

### Използвани Технологии

- **Chart.js**: За графики и визуализации
- **Leaflet**: За интерактивна карта
- **Bootstrap**: За responsive дизайн
- **jQuery**: За AJAX и DOM манипулации

## 🔧 API Endpoints

### Analytics Data API

```javascript
// Получаване на live статистики
GET /admin/analytics
Headers: X-Requested-With: XMLHttpRequest

Response:
{
    "stats": { ... },
    "success_rate": float,
    "today_requests": int,
    "timestamp": "ISO-8601"
}
```

## 🐛 Debug и Тестване

### Debug Script

```bash
python debug_analytics.py
```

Тестове които се изпълняват:

1. Import тестове
2. Database свързаност
3. Analytics функции
4. Web route тестове

### Test Scripts

```bash
python test_analytics_route.py  # Тест на analytics логика
python test_full_route.py       # Пълен route тест
```

## 📊 Примери за Използване

### Python API

```python
from admin_analytics import AnalyticsEngine, RequestFilter, RealtimeUpdates

# Получаване на статистики
stats = AnalyticsEngine.get_dashboard_stats(days=7)
print(f"Заявки за седмицата: {stats['totals']['period_requests']}")

# Филтриране на заявки
filtered = RequestFilter.filter_requests(
    status='Pending',
    keyword='здраве',
    page=1,
    per_page=10
)

# Геолокационни данни
geo_data = AnalyticsEngine.get_geo_data()
print(f"Заявки на картата: {len(geo_data['requests'])}")

# Последна активност
activity = RealtimeUpdates.get_recent_activity(limit=5)
```

### JavaScript API

```javascript
// AJAX заявка за live данни
$.ajax({
  url: "/admin/analytics",
  type: "GET",
  headers: { "X-Requested-With": "XMLHttpRequest" },
  success: function (data) {
    updateDashboard(data.stats);
    updateSuccessRate(data.success_rate);
  },
});

// Филтриране на заявки
function filterRequests() {
  const params = {
    status: $("#status-filter").val(),
    keyword: $("#search-input").val(),
    date_from: $("#date-from").val(),
    date_to: $("#date-to").val(),
  };

  window.location.search = $.param(params);
}
```

## 🎯 Ключови Показатели (KPIs)

1. **Общо Заявки**: Брой всички заявки в системата
2. **Успешност**: Процент завършени заявки
3. **Средно Време**: Време за обработка на заявка
4. **Активни Доброволци**: Брой активни доброволци
5. **Географско Покритие**: Брой обслужвани градове
6. **Категории**: Разпределение по тип помощ

## 🔒 Сигурност

- Всички analytics endpoints изискват admin аутентификация
- CSRF защита за всички форми
- Валидация на входни данни
- SQL injection защита чрез SQLAlchemy ORM

## 🚀 Performance

- Database заявките са оптимизирани с GROUP BY
- Използва се pagination за големи dataset-и
- AJAX за асинхронно обновяване
- Кеширане на геолокационни данни

## 📈 Бъдещо Развитие

1. **Export Функционалност**

   - CSV/Excel export
   - PDF reports
   - Scheduled reports

2. **Разширени Филтри**

   - Multi-select филтри
   - Date range picker
   - Advanced search

3. **Machine Learning**

   - Predictive analytics
   - Automated categorization
   - Trend analysis

4. **Mobile Optimization**
   - Responsive charts
   - Touch-friendly interface
   - Progressive Web App

## 🛠️ Инсталация и Настройка

### Изисквания

```
Flask
SQLAlchemy
Jinja2
Chart.js
Leaflet
Bootstrap
```

### Стартиране

```bash
# Стартиране на Flask app
python appy.py

# Достъп до analytics
http://localhost:5000/admin/analytics
```

### Debug Mode

```bash
# Debug режим
export FLASK_ENV=development
python appy.py

# Debug analytics
python debug_analytics.py
```

## 📞 Поддръжка

За въпроси и проблеми:

- Проверете debug_analytics.py
- Прегледайте Flask logs
- Тествайте с test\_\*.py файловете

---

_Документацията е актуална към 23.09.2025_
