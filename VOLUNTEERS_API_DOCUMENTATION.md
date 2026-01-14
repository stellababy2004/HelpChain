# HelpChain API - Доброволци

## Общ преглед

API-то за доброволци предоставя функционалност за намиране и управление на локациите на доброволците в системата HelpChain. Всички endpoints са достъпни под префикса `/api/volunteers/`.

## Privacy & Contact Data

By default, the `GET /api/volunteers/nearby` endpoint returns **public fields only**. Personal contact data (email, phone) is returned **only** when explicitly requested via `include_contacts=true` and only for authorized roles (`admin`, `coordinator`).

For details, see:
- [`docs/api/volunteers-nearby-privacy.md`](docs/api/volunteers-nearby-privacy.md)

## Endpoints

### 1. Намиране на доброволци в радиус

**Endpoint:** `GET /api/volunteers/nearby`

**Описание:** Връща списък с доброволци, намиращи се в зададен радиус около дадена географска точка. Използва Haversine формулата за изчисляване на разстоянието между две точки на земната повърхност.

**Query параметри:**

- `lat` (float, задължителен) - Географска ширина на централната точка (latitude)
- `lng` (float, задължителен) - Географска дължина на централната точка (longitude)
- `radius` (float, опционален, по подразбиране: 10) - Радиус на търсене в километри

**Пример заявка:**

```http
GET /api/volunteers/nearby?lat=42.6977&lng=23.3219&radius=50
```

**Успешен отговор (200 OK):**

```json
{
  "volunteers": [
    {
      "id": 1,
      "name": "Иван Иванов",
      "email": "ivan@example.com",
      "phone": "+359123456789",
      "skills": "Помощ при пазаруване",
      "location": "София",
      "latitude": 42.6977,
      "longitude": 23.3219,
      "distance_km": 0.0
    },
    {
      "id": 2,
      "name": "Мария Петрова",
      "email": "maria@example.com",
      "phone": "+359987654321",
      "skills": "Транспорт",
      "location": "Пловдив",
      "latitude": 42.1354,
      "longitude": 24.7453,
      "distance_km": 45.2
    }
  ],
  "count": 2,
  "search_location": {
    "lat": 42.6977,
    "lng": 23.3219
  },
  "radius_km": 50
}
```

**Грешки:**

- **400 Bad Request** - Невалидни координати или радиус

  ```json
  {
    "error": "Invalid coordinates or radius"
  }
  ```

- **500 Internal Server Error** - Сървърна грешка
  ```json
  {
    "error": "Описание на грешката"
  }
  ```

**Особености:**

- Връща само доброволци, които имат зададени координати (latitude и longitude не са null)
- Резултатите са сортирани по разстояние (от най-близкия към най-далечния)
- Използва Haversine формулата за точни геодезични изчисления
- За production среда се препоръчва използването на PostGIS или подобни геопространствени бази данни

---

### 2. Обновяване на локацията на доброволец

**Endpoint:** `PUT /api/volunteers/{volunteer_id}/location`

**Описание:** Обновява географските координати и/или текстовото описание на локацията на конкретен доброволец.

**Path параметри:**

- `volunteer_id` (integer, задължителен) - ID на доброволеца

**Request body (JSON):**

```json
{
  "latitude": 42.6977,
  "longitude": 23.3219,
  "location": "София, България"
}
```

**Параметри на тялото:**

- `latitude` (float, задължителен) - Географска ширина
- `longitude` (float, задължителен) - Географска дължина
- `location` (string, опционален) - Текстово описание на локацията (населено място, адрес и т.н.)

**Пример заявка:**

```http
PUT /api/volunteers/1/location
Content-Type: application/json

{
  "latitude": 42.6977,
  "longitude": 23.3219,
  "location": "София"
}
```

**Успешен отговор (200 OK):**

```json
{
  "success": true,
  "volunteer_id": 1,
  "location": {
    "lat": 42.6977,
    "lng": 23.3219,
    "location": "София"
  }
}
```

**Грешки:**

- **400 Bad Request** - Липсват задължителни параметри или невалидни координати

  ```json
  {
    "error": "latitude and longitude required"
  }
  ```

  или

  ```json
  {
    "error": "Invalid coordinates"
  }
  ```

- **404 Not Found** - Доброволецът не е намерен

  ```json
  {
    "error": "Volunteer not found"
  }
  ```

- **500 Internal Server Error** - Сървърна грешка
  ```json
  {
    "error": "Описание на грешката"
  }
  ```

**Особености:**

- Ако `location` не е предоставен, текстовото описание остава непроменено
- Координатите се конвертират към float преди записване
- Промените се записват веднага в базата данни с `db.session.commit()`

## Модел на данни

### Volunteer

```python
class Volunteer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    skills = db.Column(db.String(500), nullable=True)
    location = db.Column(db.String(100), nullable=True)  # Текстово описание
    latitude = db.Column(db.Float, nullable=True)        # Географска ширина
    longitude = db.Column(db.Float, nullable=True)       # Географска дължина
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
```

## Технически детайли

### Геодезични изчисления

Функцията `get_nearby_volunteers` използва Haversine формулата за изчисляване на разстоянието между две точки на сферата:

```python
def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371  # Радиус на Земята в км
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = (
        sin(dlat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    )
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c
```

### Валидация

- Координатите се валидират като float стойности
- Радиусът трябва да бъде положително число
- ID на доброволеца трябва да бъде валиден integer

### Производителност

- За големи набори от данни се препоръчва индексиране на latitude и longitude колоните
- За production системи се препоръчва използването на специализирани геопространствени бази данни като PostGIS

## Примери за използване

### JavaScript (Fetch API)

```javascript
// Намиране на доброволци в радиус
const findNearbyVolunteers = async (lat, lng, radius = 10) => {
  const response = await fetch(
    `/api/volunteers/nearby?lat=${lat}&lng=${lng}&radius=${radius}`,
  );
  const data = await response.json();
  return data;
};

// Обновяване на локация
const updateVolunteerLocation = async (volunteerId, lat, lng, location) => {
  const response = await fetch(`/api/volunteers/${volunteerId}/location`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      latitude: lat,
      longitude: lng,
      location: location,
    }),
  });
  const data = await response.json();
  return data;
};
```

### Python (requests)

```python
import requests

# Намиране на доброволци
def find_nearby_volunteers(lat, lng, radius=10):
    response = requests.get(f'/api/volunteers/nearby?lat={lat}&lng={lng}&radius={radius}')
    return response.json()

# Обновяване на локация
def update_volunteer_location(volunteer_id, lat, lng, location=None):
    data = {
        'latitude': lat,
        'longitude': lng
    }
    if location:
        data['location'] = location

    response = requests.put(f'/api/volunteers/{volunteer_id}/location', json=data)
    return response.json()
```

## Тестване

За тестване на endpoints можете да използвате pytest с `test_api_volunteers.py`:

```bash
# Стартиране на всички тестове
python -m pytest test_api_volunteers.py -v

# Стартиране на конкретен тест
python -m pytest test_api_volunteers.py::TestVolunteerAPI::test_get_nearby_volunteers_success -v
```

Тестовете покриват:

- Успешни сценарии
- Невалидни входни данни
- Грешки при липса на данни
- Частични обновявания</content>
  <parameter name="filePath">c:\Users\Stella Barbarella\OneDrive\Documents\chatGPT\Projet BG\HelpChain\VOLUNTEERS_API_DOCUMENTATION.md
