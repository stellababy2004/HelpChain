# Volunteers Nearby API - Privacy and Contacts

## Overview

- Endpoint: `GET /api/volunteers/nearby`
- Default behavior: return only public fields and exclude contact details such as email and phone.
- Contact fields are included only when `include_contacts=true` and the caller is authorized.

## Default Behavior

### Request

```http
GET /api/volunteers/nearby?lat=42.6977&lng=23.3219&radius=10
Authorization: Bearer <ACCESS_TOKEN>
```

### Response Example

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

Email and phone are not returned by default.

## Including Contacts

Contact details are included only if both conditions are true:

- `include_contacts=true`
- the caller has role `admin` or `coordinator`

### Request

```http
GET /api/volunteers/nearby?lat=42.6977&lng=23.3219&radius=10&include_contacts=true
Authorization: Bearer <ACCESS_TOKEN>
```

### Response Example

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

## Authorization Rules

- `admin` can receive contacts
- `coordinator` can receive contacts
- other roles do not receive contacts even if `include_contacts=true`

## Design Rationale

- Privacy first: personal contact data is excluded by default.
- Explicit intent: contact access requires both a request flag and authorization.
- Future-safe contract: location-based discovery can evolve without changing the privacy baseline.

## Change Note

Version `v1.0` establishes the default public-fields response, with contact disclosure limited to authorized admin or coordinator access.
