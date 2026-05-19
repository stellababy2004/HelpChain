# HelpChain

HelpChain is an operational coordination platform for social-sector organisations, local structures and professional networks.

It helps teams centralise incoming requests, qualify situations, assign responsibilities, coordinate trusted actors and keep a clear operational history.

## Positioning

HelpChain is designed as a coordination infrastructure, not a public marketplace.

The platform focuses on:

- structured intake of social requests;
- controlled orientation between authorised actors;
- role-based access and visibility;
- operational traceability;
- territory-level monitoring;
- progressive deployment for organisations.

## Core Capabilities

### Public and organisational intake

- Submit requests through structured forms
- Route information to the appropriate operational workflow
- Keep requesters outside unnecessary account complexity
- Preserve a clear record of status and follow-up

### Operational workspace

- Manage requests, cases and assignments
- Track status changes and operational activity
- Coordinate volunteers, professionals and partner structures
- Monitor pending, active and closed situations

### Admin and pilotage

- Admin dashboard
- Case and request lifecycle management
- Professional and volunteer assignment
- Audit-oriented activity tracking
- Operational maps and territorial views
- KPI and reporting surfaces

### Security and governance

- Role-based access control
- Scoped administrative access
- Traceability of actions
- Controlled data visibility
- GDPR-oriented operating model

## Technical Stack

- Backend: Flask, SQLAlchemy, Alembic
- Frontend: Jinja templates, Bootstrap, custom CSS and JavaScript
- Database: SQLite for local development, PostgreSQL-ready for production
- Auth: session-based admin and user authentication
- Deployment: production-ready Flask stack
- Internationalisation: French-first, with multilingual support in progress

## Development

Apply database migrations locally:

`ash
export FLASK_APP=backend.helpchain_backend.src.app
flask db upgrade
