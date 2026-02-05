# HelpChain

HelpChain is a social-impact platform that connects people in need with verified volunteers and professionals.

The project focuses on:
- Simple access (no mandatory accounts for requesters)
- Human-centered UX
- Secure and traceable request handling
- Gradual scalability (MVP → production)

---

## Current Features (MVP)

### Requesters (no login)
- Submit a help request
- Access a private requester profile via a secure magic link
- Track request status updates

### Volunteers
- Volunteer authentication
- Dashboard with available and assigned requests
- Status-based workflow (open → in progress → done)

### Admin
- Admin dashboard
- Request lifecycle management
- Volunteer assignment
- Audit & status tracking

---

## Technical Stack

- **Backend:** Flask, SQLAlchemy, Alembic
- **Frontend:** Jinja templates, Bootstrap, custom CSS
- **Database:** SQLite (dev), PostgreSQL-ready
- **Auth:** Session-based (volunteer/admin), magic-link (requester)
- **i18n:** FR / BG / EN

---

## Database Migrations

This project uses Flask-Migrate (Alembic).

To apply migrations locally:

```bash
export FLASK_APP=backend.helpchain_backend.src.app
flask db upgrade
```

---

## Development Notes

- Requesters do not need to create an account (MVP decision).
- Magic links are token-based and stored hashed in the database.
- Expiry and revocation policies will be added in the next iteration.

### Status

🚧 Active development (MVP phase)
