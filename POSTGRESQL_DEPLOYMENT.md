# PostgreSQL Deployment Guide for HelpChain

## Overview

This guide covers deploying the HelpChain application to PostgreSQL databases in cloud environments like Render, Heroku, or AWS RDS.

## Prerequisites

- PostgreSQL database instance
- Python 3.8+
- All dependencies from `requirements.txt`

## Database Setup

### 1. Environment Configuration

Set the `DATABASE_URL` environment variable:

```bash
# For Render/Heroku
export DATABASE_URL="postgresql://username:password@host:port/database"

# For local PostgreSQL
export DATABASE_URL="postgresql://helpchain_user:password@localhost:5432/helpchain_db"
```

### 2. Run Database Migrations

```bash
# Initialize and run migrations
python setup_postgresql.py
```

### 3. Alternative Manual Migration

If the setup script fails, run migrations manually:

```bash
# Set database URL
export DATABASE_URL="your_postgresql_connection_string"

# Run migrations
alembic upgrade head
```

## Cloud Deployment Examples

### Render

1. Create a PostgreSQL database instance
2. Set `DATABASE_URL` in environment variables
3. Deploy with the build command:
   ```bash
   pip install -r requirements.txt
   python setup_postgresql.py
   ```

### Heroku

1. Add Heroku Postgres add-on
2. The `DATABASE_URL` is automatically set
3. Deploy normally - migrations run automatically

### Docker Deployment

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
RUN python setup_postgresql.py

CMD ["python", "run.py"]
```

## Database Features

### PostgreSQL-Specific Optimizations

- **Enum Types**: Custom enum types for roles, permissions, priorities, etc.
- **JSON Fields**: For flexible data storage (analytics, metadata)
- **Timezone-Aware Timestamps**: Proper UTC handling
- **Performance Indexes**: Optimized for common queries

### Indexes Created

- Users: email, phone, location
- Help Requests: status, priority, location, created_at
- Volunteers: skills, location, availability
- Notifications: user_id, status, created_at
- User Activities: user_id, activity_type, timestamp

## Troubleshooting

### Common Issues

**Migration Fails with Enum Errors**

```bash
# Drop and recreate database, then rerun migrations
alembic downgrade base
alembic upgrade head
```

**Connection Timeout**

- Check firewall settings
- Verify connection string format
- Ensure database accepts connections from your IP

**Permission Errors**

- Grant proper permissions to database user
- Check PostgreSQL user roles

### Testing Migrations

Run the local test script to verify migration compatibility:

```bash
python test_migrations.py
```

## Database Schema

### Core Tables

- `users` - End users
- `admin_users` - Administrative users with 2FA
- `volunteers` - Volunteer profiles
- `help_requests` - Help request submissions
- `notifications` - System notifications
- `user_activities` - Analytics tracking

### Supporting Tables

- `roles` & `permissions` - RBAC system
- `chat_*` - Chat functionality
- `audit_logs` - Security auditing

## Performance Considerations

### Connection Pooling

For production, configure connection pooling:

```python
# In production config
SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_size': 10,
    'max_overflow': 20,
    'pool_timeout': 30,
    'pool_recycle': 3600
}
```

### Monitoring

Monitor these metrics:

- Connection count
- Query performance
- Index usage
- Table sizes

## Backup Strategy

- Daily automated backups
- Point-in-time recovery capability
- Test restore procedures regularly

## Security

- Use strong database passwords
- Restrict database access by IP
- Enable SSL connections
- Regular security updates
