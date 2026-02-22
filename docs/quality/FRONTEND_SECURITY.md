# HelpChain – Frontend Security Rules

This document defines baseline frontend security practices for templates, JS, and UI integrations.

---

## 1. XSS Safety

- Never inject untrusted content with `innerHTML`.
- Prefer `textContent` and `createElement`.
- If HTML rendering is required, sanitize on the server and keep a strict allowlist.
- Treat `|safe` in Jinja as privileged: use only for static, controlled strings.

---

## 2. Template Safety (Jinja)

- Use autoescaping defaults.
- Avoid string concatenation for raw HTML when data is dynamic.
- Escape user content in attributes and text nodes.
- Keep IDs deterministic for a11y/form linking, not from untrusted input.

---

## 3. CSRF

- Use one global pattern:
  - `<meta name="csrf-token" content="{{ csrf_token() }}">`
  - `X-CSRFToken` header for JS `POST/PUT/PATCH/DELETE`
  - hidden `csrf_token` input for HTML forms
- Do not mix legacy `csrf_form` injection with token-only flow.

---

## 4. Event Handlers and CSP Readiness

- Prefer `addEventListener` over inline `onclick`.
- Avoid inline scripts where possible; move to static JS files.
- Keep code compatible with strict CSP (`script-src` without unsafe-inline) as a target.

---

## 5. Client Storage

- Store only non-sensitive UI preferences in `localStorage` (theme/a11y toggles).
- Never store auth tokens, secrets, or PII in browser storage.

---

## 6. External Content and Links

- Add `rel="noopener noreferrer"` for external links opened with `target="_blank"`.
- Validate and allowlist external script/style sources.
- Pin CDN versions explicitly.

---

## 7. Accessibility + Security Intersection

- Security controls must stay accessible:
  - keyboard reachable
  - focus visible
  - clear error states
- Validation and anti-bot controls must not block assistive tech users.

---

## 8. Review Checklist (PR)

- [ ] No unsafe `innerHTML` usage for dynamic content
- [ ] No new unsafe `|safe` usage with user-controlled content
- [ ] CSRF token present for all state-changing actions
- [ ] External links using `target="_blank"` include `rel="noopener noreferrer"`
- [ ] No secrets/PII stored in localStorage/sessionStorage

