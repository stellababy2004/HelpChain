# Security Standards – Code & Operations

## Code Security

- Follow PEP8 & Flask best practices.
- Use parameterized queries (SQLAlchemy ORM).
- No hardcoded secrets → use `.env` + `Flask config`.
- CSRF enabled via `Flask-WTF`.
- Input validation & output sanitization required.
- CodeQL & Dependabot active in all repos.

## Operational Security

- Enforce HTTPS (TLS 1.3).
- DMARC policy: `p=reject`.
- Use least-privilege API tokens.
- Audit admin actions monthly.

## Vulnerability Management

1. Review Dependabot alerts weekly.
2. Patch CVEs within 48 hours.
3. Verify fix and redeploy.
