# HelpChain API Documentation

## Общ преглед

HelpChain API предоставя RESTful интерфейс за взаимодействие с платформата за социална и здравна подкрепа. API-то поддържа JSON формат за данни и използва стандартни HTTP методи.

## Базов URL

```
https://helpchain.live/api/
```

За локална разработка:

```
http://127.0.0.1:3000/api/
```

## Автентикация

### Admin автентикация

Администраторският достъп изисква 2FA (двуфакторна автентикация) по имейл.

```bash
# 1. Вход с credentials
POST /admin_login
Content-Type: application/x-www-form-urlencoded

username=admin&password=admin123

# 2. Въвеждане на 2FA код (изпратен по имейл)
POST /admin/email_2fa
Content-Type: application/x-www-form-urlencoded

code=123456
```

### Volunteer автентикация

```bash
# Вход по имейл (без парола - само проверка на съществуване)
POST /volunteer_login
Content-Type: application/x-www-form-urlencoded

email=volunteer@example.com
```

## Endpoints

### Основни

#### GET /

**Описание:** Главна страница с основна информация
**Отговор:**

```json
{
  "volunteers_count": 42,
  "requests_count": 15,
  "open_requests": 8
}
```

#### GET /all_categories

**Описание:** Всички налични категории помощ
**Отговор:**

```json
{
  "categories": [
    {
      "slug": "medical",
      "name": "Спешна помощ",
      "icon": "fas fa-ambulance",
      "color": "danger",
      "description": "Медицинска помощ, спешни случаи"
    }
  ]
}
```

#### POST /volunteer_register

**Описание:** Регистрация на нов доброволец
**Body:**

```json
{
  "name": "Иван Петров",
  "email": "ivan@example.com",
  "phone": "+359 88 123 4567",
  "location": "София"
}
```

**Отговор:** Редирект към регистрационна страница с флаш съобщение

#### POST /submit_request

**Описание:** Подаване на заявка за помощ
**Body (form-data):**

```
name: Мария Иванова
email: maria@example.com
category: medical
location: София
problem: Нуждая се от спешна медицинска помощ
captcha: 7G5K
file: [uploaded_file] (опционално)
```

**Отговор:** Редирект към success страница

### Геолокационни API

#### GET /api/volunteers/nearby

**Описание:** Намиране на доброволци в определен радиус
**Параметри:**

- `lat` (float): Географска ширина
- `lng` (float): Географска дължина
- `radius` (float, опционално): Радиус в км (default: 10)

**Пример:**

```bash
GET /api/volunteers/nearby?lat=42.6977&lng=23.3219&radius=50
```

**Отговор:**

```json
{
  "volunteers": [
    {
      "id": 1,
      "name": "Иван Петров",
      "email": "ivan@example.com",
      "phone": "+359 88 123 4567",
      "skills": "Първа помощ",
      "location": "София",
      "latitude": 42.6977,
      "longitude": 23.3219,
      "distance_km": 2.5
    }
  ],
  "count": 1,
  "search_location": {
    "lat": 42.6977,
    "lng": 23.3219
  },
  "radius_km": 50
}
```

#### PUT /api/volunteers/{volunteer_id}/location

**Описание:** Обновяване на локацията на доброволец
**Headers:**

```
Content-Type: application/json
```

**Body:**

```json
{
  "latitude": 42.6977,
  "longitude": 23.3219,
  "location": "София, България"
}
```

**Отговор:**

```json
{
  "success": true,
  "volunteer_id": 1,
  "location": {
    "lat": 42.6977,
    "lng": 23.3219,
    "text": "София, България"
  }
}
```

### Административни endpoints

#### GET /admin_volunteers

**Описание:** Списък с доброволци (само за администратори)
**Параметри:**

- `search` (string): Търсене по име, имейл, телефон
- `location` (string): Филтър по локация
- `sort` (string): Сортиране (name, location, created_at)
- `order` (string): Ред на сортиране (asc, desc)
- `page` (int): Страница (default: 1)
- `per_page` (int): Резултати на страница (default: 25)

#### POST /admin_volunteers/add

**Описание:** Добавяне на нов доброволец
**Body:**

```
name: Нов доброволец
email: new@example.com
phone: +359 88 123 4567
location: София
```

#### POST /admin_volunteers/edit/{id}

**Описание:** Редактиране на доброволец
**Body:**

```
name: Променено име
email: updated@example.com
phone: +359 88 987 6543
location: Пловдив
```

#### POST /delete_volunteer/{id}

**Описание:** Изтриване на доброволец

#### GET /export_volunteers

**Описание:** Експорт на доброволци
**Параметри:**

- `format` (string): csv, json, pdf (default: csv)
- `search`, `location`: Същите като в /admin_volunteers

### Аналитични endpoints

#### GET /admin/analytics/dashboard

**Описание:** Основни метрики за dashboard
**Отговор:**

```json
{
  "total_volunteers": 42,
  "active_volunteers": 38,
  "total_requests": 156,
  "completed_requests": 134,
  "pending_requests": 22,
  "avg_response_time": "2.5 часа",
  "top_categories": [
    { "name": "Медицинска помощ", "count": 45 },
    { "name": "Транспорт", "count": 32 }
  ]
}
```

## Грешки

API-то връща стандартни HTTP статус кодове:

- `200 OK` - Успешна операция
- `302 Found` - Редирект (при форми)
- `400 Bad Request` - Невалидни данни
- `401 Unauthorized` - Липса на автентикация
- `403 Forbidden` - Недостатъчни права
- `404 Not Found` - Ресурсът не е намерен
- `500 Internal Server Error` - Сървърна грешка

**Пример за грешка:**

```json
{
  "error": "Invalid coordinates",
  "message": "Latitude and longitude must be valid numbers"
}
```

## Rate Limiting

API-то има защити срещу злоупотреба:

- **Общи лимити:** 200 заявки/ден, 50/час на IP
- **Логин форми:** 5 опита/минута, 20/час
- **Регистрации:** 10/минута, 50/час
- **Обратна връзка:** 3/минута, 10/час

## WebSocket (Real-time)

За видео чат функционалност се използва Socket.IO:

### Събития

#### Клиент → Сървър

- `join_room`: Присъединяване към стая
- `offer`: WebRTC offer
- `answer`: WebRTC answer
- `ice_candidate`: ICE кандидат
- `leave_room`: Напускане на стая
- `chat_message`: Текстови съобщения

#### Сървър → Клиент

- `user_joined`: Нов потребител се присъедини
- `user_left`: Потребител напусна
- `offer`: Получен WebRTC offer
- `answer`: Получен WebRTC answer
- `ice_candidate`: Получен ICE кандидат
- `chat_message`: Ново съобщение

**Пример за присъединяване:**

```javascript
socket.emit("join_room", {
  room: "request_123",
  user_type: "volunteer",
  user_id: 1,
  user_name: "Иван Петров",
});
```

## Безопасност

- Всички чувствителни данни се хешират
- CSRF защита на форми
- Rate limiting срещу brute force
- Input validation и sanitization
- Secure headers (HSTS, CSP, etc.)
- 2FA за администраторски достъп

## Версии

- **v1.0** (текуща): Основен API с геолокация и управление на доброволци
- **v0.9** (beta): Първоначална версия с основни функции

## Поддръжка

За въпроси относно API-то:

- **Email:** contact@helpchain.live
- **Документация:** https://helpchain.live/api/docs
- **GitHub Issues:** https://github.com/stellababy2004/HelpChain.bg/issues
