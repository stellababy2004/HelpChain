# HelpChain Backend - AI Agent Instructions

## Architecture Overview

HelpChain is a Flask-based help request platform with volunteer matching, analytics, and real-time features. Key components:

- **Core App** (`appy.py`): Main Flask application with extensions (SQLAlchemy, Redis, SocketIO, Celery)
- **Models** (`models.py`, `models_with_analytics.py`): User roles (user/volunteer/admin), help requests, analytics events
- **Analytics** (`analytics_service.py`, `advanced_analytics.py`): ML-powered insights using scikit-learn/pandas
- **AI Service** (`ai_service.py`): Smart volunteer-request matching
- **Permissions** (`permissions.py`): Role-based access control with granular permissions

## Data Flow

1. Users submit help requests via web forms
2. AI service matches requests to volunteers based on skills/location
3. Real-time chat via SocketIO, notifications via email/app
4. Analytics track all interactions, predict patterns, detect anomalies

## Critical Workflows

- **Development Server**: `python start_server.py` (debug=True, host=127.0.0.1:5000)
- **Testing**: `pytest` (tests in `tests/` dir, PYTHONPATH=., conftest.py fixtures)
- **Database**: Alembic migrations (`alembic upgrade head`), PostgreSQL in prod, SQLite in dev
- **Caching**: Redis for sessions/analytics, configured in `extensions.py`
- **Background Tasks**: Celery (`celery_app.py`) for email notifications, analytics processing
- **Deployment**: Docker/K8s manifests in repo root, `make k8s-deploy`

## Project Conventions

- **Imports**: Use absolute imports with try/except fallbacks (e.g., `from extensions import db` with fallback)
- **Database Access**: Always use `get_db()` from app context, never global db instances
- **Models**: Enums for roles/permissions (e.g., `RoleEnum.admin`), string relationships to avoid circular imports
- **Analytics**: Track events via `AnalyticsEvent` model, use pandas for data processing
- **Security**: 2FA via pyotp, rate limiting via Flask-Limiter, Talisman for headers
- **Multilingual**: Flask-Babel with .pot files, Bulgarian as primary language
- **Error Handling**: Generic 500 errors (no tracebacks in prod), logging to files
- **File Structure**: `static/` for assets, `templates/` for Jinja2, `tests/` for pytest

## Integration Points

- **External APIs**: Email via Flask-Mail (SMTP), SMS via custom service
- **WebSockets**: Real-time chat/notifications via Flask-SocketIO
- **ML Models**: Persisted in `uploads/`, loaded via joblib
- **Caching**: Redis for performance, Flask-Caching for views
- **Monitoring**: Sentry for error tracking, custom performance metrics

## Common Patterns

- **Route Protection**: `@require_permission(PermissionEnum.ADMIN_ACCESS)` decorator
- **Analytics Tracking**: `analytics_service.track_event('page_view', user_id=user.id)`
- **Async Tasks**: `@celery_app.task` for background processing
- **Model Queries**: Use SQLAlchemy text() for complex queries, func.count() for aggregations
- **Testing**: Mock external services (SMTP, HTTP), use fixtures from conftest.py

## Key Files to Reference

- `appy.py`: Main app setup and routes
- `models.py`: Core data models and enums
- `analytics_service.py`: Analytics logic and ML integration
- `permissions.py`: Access control implementation
- `requirements.txt`: All dependencies with versions
- `DEVELOPMENT_ROADMAP.md`: Current priorities and architecture decisions</content>
  <parameter name="filePath">c:\Users\Stella Barbarella\OneDrive\Documents\chatGPT\Projet BG\HelpChain\backend\.github\copilot-instructions.md
