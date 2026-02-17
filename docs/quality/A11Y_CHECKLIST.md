# HelpChain – Accessibility Regression Checklist (V1)

Run this checklist after UI or layout changes (5–10 minutes total).

---

## 1. Global Accessibility Drawer (♿)

- [ ] Tab to ♿ button -> Enter opens drawer
- [ ] Focus moves inside drawer (first interactive element)
- [ ] Tab cycles inside drawer (focus trap works)
- [ ] Esc closes drawer
- [ ] Focus returns to ♿ button
- [ ] Body scroll is locked while drawer is open

---

## 2. Preference Persistence (localStorage)

- [ ] High contrast persists after refresh
- [ ] Bigger text persists after refresh
- [ ] Reduce motion persists after refresh
- [ ] Simplified mode persists after refresh

---

## 3. Simplified Mode (Manual Task Mode)

### Home Page

- [ ] Only core actions remain visible:
  - Submit a request
  - Become volunteer / Login
  - Contact / Emergency info
- [ ] Non-essential sections hidden (`.hc-optional` / `.hc-secondary`)
- [ ] Layout becomes more compact (reduced spacing)

### Volunteer Dashboard

- [ ] Filters remain visible (min/prio/near/apply)
- [ ] Match cards remain visible
- [ ] CTA buttons remain visible
- [ ] Informational subtitles/banners hidden
- [ ] Empty state still visible if no matches

---

## 4. Submit Request Form (Inline Validation)

- [ ] Invalid POST returns 400 (no redirect)
- [ ] Inline field errors render correctly
- [ ] Form-level summary renders
- [ ] "Go to first error" link anchors properly
- [ ] Focus moves to first invalid field

---

## 5. Match Modal ("Why %?")

- [ ] Opens from card button
- [ ] Esc closes modal
- [ ] Focus returns to trigger
- [ ] No innerHTML usage for breakdown rendering
- [ ] Progress bars expose aria-valuenow/min/max

---

## 6. Keyboard Navigation

- [ ] No keyboard traps
- [ ] Logical tab order
- [ ] Visible focus states
- [ ] All actionable elements reachable via keyboard

---

## 7. Reduced Motion

- [ ] Animations minimized when reduced motion enabled
- [ ] No scroll-behavior smooth in reduced mode

---

## Known Development Notes

- SQLite warning `malformed database schema (ix_requests_requester_token_hash)` is a local DB issue.
- Not related to accessibility or UI layer.
