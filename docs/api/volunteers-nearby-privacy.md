# Volunteers Nearby API – Privacy & Contacts

## Overview
- Endpoint: `GET /api/volunteers/nearby`
- Default: връща само публични полета (без email/phone).
- Контактите се добавят само при `include_contacts=true` и роля `admin` или `coordinator`.

## Default Behavior (без контакти)
**Request**
```
GET /api/volunteers/nearby?lat=42.6977&lng=23.3219&radius=10
Authorization: Bearer <ACCESS_TOKEN>
```

**Response (пример)**
```json
{
  "count": 1,
  "radius_km": 10.0,
  "search_location": { "lat": 42.6977, "lng": 23.3219 },
  "volunteers": [
    {
      "id": 1,
      "name": "Test Volunteer",
      "location": "Sofia",
      "latitude": 42.6977,
      "longitude": 23.3219,
      "distance_km": 0.0,
      "skills": null
    }
  ]
}
```
> email/phone не се връщат.

## Включване на контакти (изрично + авторизирано)
Контактите се добавят само ако:
- `include_contacts=true`, и
- роля: `admin` или `coordinator`.

**Request**
```
GET /api/volunteers/nearby?lat=42.6977&lng=23.3219&radius=10&include_contacts=true
Authorization: Bearer <ACCESS_TOKEN>
```

**Response (пример)**
```json
{
  "count": 1,
  "radius_km": 10.0,
  "search_location": { "lat": 42.6977, "lng": 23.3219 },
  "volunteers": [
    {
      "id": 1,
      "name": "Test Volunteer",
      "location": "Sofia",
      "latitude": 42.6977,
      "longitude": 23.3219,
      "distance_km": 0.0,
      "skills": null,
      "email": "testvol@example.com",
      "phone": "+3590000000"
    }
  ]
}
```

**Authorization rules**
- `admin` → contacts allowed
- `coordinator` → contacts allowed
- others → contacts се игнорират, дори при `include_contacts=true`.

## Причини за този дизайн
- Privacy-first: няма лични данни по подразбиране.
- Explicit intent: контакти само при ясно искане + права.
- Future-proof: готово за карта/координатор без refactor.

## Changelog
- v1.0 – Default публични полета; `include_contacts=true` показва контакти само за admin/coordinator.
