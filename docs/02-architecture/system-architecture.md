# System Architecture

## Overview

HelpChain is a Flask-based web application using server-rendered templates, modular backend routes and a relational database.

The platform is structured around:

- public pages
- admin workspace
- operator workspace
- request management
- case management
- professional lead management
- notifications
- audit and activity logs
- KPI and risk surfaces

## Core stack

- Python / Flask
- SQLAlchemy
- Alembic migrations
- Jinja templates
- PostgreSQL in production
- SQLite for local development
- Render deployment
- Neon Postgres database
- GitHub Actions
- AWS S3 backups

## Main operational concepts

- Structure: tenant or organization using the platform
- Service: internal service/team inside a structure
- Request: incoming need or operational demand
- Case: structured follow-up object linked to a request
- Admin user: privileged user managing operations
- Operator: user focused on daily operational queue handling
- Intervenant: person or actor assigned to intervention/follow-up
