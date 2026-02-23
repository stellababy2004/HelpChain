# HelpChain – UX Rules

Practical UX rules for shipping consistent, low-friction interfaces.

---

## 1. Core Action Priority

Every page should make primary actions obvious and reachable.

- Home core actions:
  - Submit a request
  - Become volunteer / Login
  - Contact / Emergency info
- Do not hide core actions behind advanced controls.

---

## 2. Simplified Mode

Simplified mode is a focus mode, not a broken layout.

- Keep primary actions, forms, and key status visible.
- Hide optional/informational noise via:
  - `.hc-optional`
  - `.hc-secondary`
  - `.hc-decor`
- Reduce spacing/density for faster scanning.

---

## 3. Form UX

- Inline validation first (no redirect on validation errors).
- Return `400` for invalid form submissions.
- Show:
  - field-level errors (`is-invalid` + feedback)
  - form-level summary with anchor to first error
- Move focus to first invalid control.

---

## 4. CTA Semantics

- Different buttons should represent different intent.
- If destination is shared, pass explicit intent (e.g. `?intent=help`).
- Avoid duplicate labels/actions that feel identical but mean different things.

---

## 5. Cards and Lists

- Keep title as a link to details.
- Keep explicit CTA buttons for key actions.
- Do not make entire cards clickable if it conflicts with nested controls.

---

## 6. Modals/Drawers

- Must support keyboard fully:
  - open focus
  - focus trap
  - Esc close
  - return focus to trigger
- For dynamic content, use DOM builders over HTML string injection.

---

## 7. Feedback and Status

- Success/warning/error messaging should be immediate and clear.
- Avoid ambiguous states: each status must imply a next action.
- Keep empty states actionable (profile completion, filters, next step).

---

## 8. Internationalization

- User-facing strings go through `_()`.
- Do not leave mixed hardcoded languages in the same interaction path.
- Keep labels concise and consistent across locales.

---

## 9. Regression Checklist Link

After UI changes, run:

- `docs/quality/A11Y_CHECKLIST.md`

UX quality is complete only when accessibility and interaction checks both pass.

