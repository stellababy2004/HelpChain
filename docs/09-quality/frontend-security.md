# Frontend Security

This document defines baseline frontend security expectations for templates, JavaScript, and browser-side integrations.

## XSS Safety

- Never inject untrusted content with `innerHTML`.
- Prefer `textContent` and DOM construction helpers.
- If HTML rendering is required, sanitize on the server with a strict allowlist.
- Treat Jinja `|safe` as privileged usage only.

## Template Safety

- Keep autoescaping enabled by default.
- Avoid assembling dynamic HTML strings from user content.
- Escape user-controlled values in both text and attribute contexts.

## CSRF

Use one consistent approach for state-changing requests:

- meta tag token for JavaScript requests
- `X-CSRFToken` header for non-GET requests
- hidden `csrf_token` field for HTML forms

Avoid mixing incompatible legacy patterns.

## CSP Readiness

- Prefer `addEventListener` over inline event handlers.
- Move inline scripts into static assets where practical.
- Keep new frontend code compatible with a stricter CSP posture.

## Browser Storage

- Store only non-sensitive UI preferences in browser storage.
- Never store auth tokens, credentials, secrets, or PII in `localStorage` or `sessionStorage`.

## External Content

- Use `rel="noopener noreferrer"` with `target="_blank"`.
- Allowlist external scripts and styles.
- Pin third-party asset versions explicitly.
