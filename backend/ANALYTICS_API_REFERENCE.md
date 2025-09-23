# 🔗 HelpChain Analytics API Reference

## Overview

Comprehensive API documentation for HelpChain Analytics system components.

## 📚 Classes and Methods

### AnalyticsEngine

#### `get_dashboard_stats(days: int = 30) -> dict`

Retrieves comprehensive dashboard statistics.

**Parameters:**
- `days` (int, optional): Analysis period in days. Default: 30

**Returns:**
```python
{
    "totals": {
        "requests": int,           # Total help requests
        "volunteers": int,         # Total volunteers
        "users": int,             # Total users
        "period_requests": int    # Requests in specified period
    },
    "status_stats": {
        "status_name": int,       # Count by status
        ...
    },
    "daily_stats": [
        {
            "date": "DD.MM",      # Date in DD.MM format
            "requests": int,      # Requests count
            "volunteers": int     # Volunteers count
        },
        ...
    ],
    "location_stats": {
        "location": int,          # Count by location
        ...
    },
    "category_stats": {
        "category": int,          # Count by category
        ...
    },
    "period_days": int           # Analysis period
}
```

#### `get_daily_stats(days: int = 30) -> list`

Retrieves daily statistics for charts.

**Parameters:**
- `days` (int, optional): Number of days to analyze. Default: 30

**Returns:**
```python
[
    {
        "date": "DD.MM",
        "requests": int,
        "volunteers": int
    },
    ...
]
```

#### `get_location_stats() -> dict`

Analyzes distribution by geographic locations.

**Returns:**
```python
{
    "location_name": int,  # Count of volunteers by location
    ...
}
```

#### `get_category_stats() -> dict`

Categorizes requests based on keywords.

**Categories:**
- `здраве`: Health-related requests
- `документи`: Document-related requests
- `социална помощ`: Social assistance
- `транспорт`: Transportation
- `образование`: Education
- `друго`: Other

**Returns:**
```python
{
    "category_name": int,  # Count by category
    ...
}
```

#### `get_geo_data() -> dict`

Retrieves geographic data for map visualization.

**Returns:**
```python
{
    "requests": [
        {
            "id": int,
            "name": str,
            "title": str,
            "status": str,
            "lat": float,
            "lng": float,
            "type": "request",
            "created_at": str
        },
        ...
    ],
    "volunteers": [
        {
            "id": int,
            "name": str,
            "location": str,
            "lat": float,
            "lng": float,
            "type": "volunteer"
        },
        ...
    ],
    "centers": [
        {
            "city": str,
            "lat": float,
            "lng": float,
            "volunteer_count": int,
            "type": "center"
        },
        ...
    ]
}
```

#### `get_success_rate() -> float`

Calculates success rate of completed requests.

**Returns:**
- `float`: Success rate as percentage (0-100)

### RequestFilter

#### `filter_requests(**kwargs) -> dict`

Filters requests based on multiple criteria.

**Parameters:**
- `status` (str, optional): Request status filter
- `date_from` (datetime, optional): Start date filter
- `date_to` (datetime, optional): End date filter
- `location` (str, optional): Location filter
- `keyword` (str, optional): Text search in title/description
- `category` (str, optional): Category filter
- `priority` (str, optional): Priority filter
- `page` (int, optional): Page number. Default: 1
- `per_page` (int, optional): Items per page. Default: 20

**Returns:**
```python
{
    "items": [HelpRequest, ...],  # List of filtered requests
    "total": int,                 # Total matching items
    "pages": int,                 # Total pages
    "current_page": int,          # Current page number
    "has_prev": bool,             # Has previous page
    "has_next": bool,             # Has next page
    "prev_num": int,              # Previous page number
    "next_num": int               # Next page number
}
```

#### `get_filter_options() -> dict`

Retrieves available filter options.

**Returns:**
```python
{
    "statuses": [str, ...],      # Available statuses
    "locations": [str, ...],     # Available locations
    "categories": [str, ...]     # Available categories
}
```

### RealtimeUpdates

#### `get_recent_activity(limit: int = 10) -> list`

Retrieves recent system activity.

**Parameters:**
- `limit` (int, optional): Maximum number of items. Default: 10

**Returns:**
```python
[
    {
        "type": str,              # Activity type: "request" or "admin_action"
        "id": int,                # Item ID
        "title": str,             # Activity title
        "description": str,       # Activity description
        "timestamp": datetime,    # Activity timestamp
        "status": str,            # Status (for requests)
        "admin_user": str         # Admin username (for admin actions)
    },
    ...
]
```

#### `get_live_stats() -> dict`

Retrieves real-time statistics for live updates.

**Returns:**
```python
{
    "timestamp": str,             # ISO timestamp
    "requests_today": int,        # Requests created today
    "requests_this_week": int,    # Requests this week
    "active_requests": int,       # Currently active requests
    "total_volunteers": int,      # Total volunteers
    "success_rate": float         # Success rate percentage
}
```

## 🌐 Web Endpoints

### `GET /admin/analytics`

Main analytics dashboard endpoint.

**Authentication:** Admin login required

**Query Parameters:**
- `page` (int): Page number
- `per_page` (int): Items per page
- `status` (str): Status filter
- `date_from` (str): Start date (YYYY-MM-DD)
- `date_to` (str): End date (YYYY-MM-DD)
- `location` (str): Location filter
- `keyword` (str): Search keyword
- `category` (str): Category filter

**AJAX Support:**
Send `X-Requested-With: XMLHttpRequest` header to receive JSON response.

**JSON Response (AJAX):**
```json
{
    "stats": { ... },           // Dashboard statistics
    "success_rate": float,      // Success rate
    "today_requests": int,      // Today's requests
    "timestamp": "ISO-8601"     // Response timestamp
}
```

**HTML Response (Normal):**
Renders `admin_analytics_dashboard.html` template with full data.

## 📊 Database Models

### HelpRequest
- `id`: Primary key
- `name`: Requester name
- `email`: Contact email
- `title`: Request title
- `description`: Detailed description
- `message`: Additional message
- `status`: Current status
- `created_at`: Creation timestamp

### Volunteer
- `id`: Primary key
- `name`: Volunteer name
- `location`: Geographic location
- `created_at`: Registration timestamp

### AdminLog
- `id`: Primary key
- `action`: Action performed
- `details`: Action details
- `timestamp`: Action timestamp
- `admin_user_id`: Admin user reference

## 🔧 Configuration

### City Coordinates (Bulgaria)
```python
city_coords = {
    'sofia': [42.6977, 23.3219],
    'plovdiv': [42.1354, 24.7453],
    'varna': [43.2141, 27.9147],
    'burgas': [42.5048, 27.4626],
    'ruse': [43.8564, 25.9706],
    'stara_zagora': [42.4258, 25.6347],
    'pleven': [43.4170, 24.6167],
    'sliven': [42.6858, 26.3253],
    'dobrich': [43.5723, 27.8274],
    'shumen': [43.2706, 26.9247]
}
```

### Category Keywords
```python
categories = {
    'здраве': ['здраве', 'болница', 'лекар', 'медицин', 'лечение'],
    'документи': ['документи', 'паспорт', 'удостоверение', 'справка'],
    'социална помощ': ['храна', 'облекло', 'парично', 'социална'],
    'транспорт': ['транспорт', 'превоз', 'автобус', 'такси'],
    'образование': ['образование', 'училище', 'университет', 'обучение'],
    'друго': []
}
```

## 🚨 Error Handling

All methods include try-catch blocks and graceful error handling:

- Database connection errors
- Invalid date formats
- Missing data handling
- Template rendering errors

## 📈 Performance Considerations

- Database queries are optimized with GROUP BY
- Pagination for large datasets
- AJAX for asynchronous updates
- Caching of geographic data
- Limited result sets for map visualization

## 🔒 Security Features

- Admin authentication required
- CSRF protection
- SQL injection protection via SQLAlchemy ORM
- Input validation and sanitization

---

*API Reference updated: 23.09.2025*