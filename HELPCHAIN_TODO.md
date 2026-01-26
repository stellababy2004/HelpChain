# HelpChain Roadmap

This file is the single source of truth for the project.  
Rule: 1 session = 1 small task.  
No chaos. No multitasking. No new features before finishing the current phase.

---

## PHASE 1 – Core Stability (CURRENT)

- [x] Admin login  
- [x] Admin requests list  
- [x] Request details page  
- [x] Assign volunteer  
- [x] Unassign volunteer  
- [x] Audit log for assign/unassign  

- [x] Add is_archived field to Request model  
- [x] DB migration for is_archived  
- [x] Hide archived requests from admin list  
- [x] Archive endpoint (POST /admin/requests/<id>/archive)  
- [x] Archive button in request_details.html  

- [x] Activity log tab in request details  
- [x] owned_at timestamp on assign  
- [x] One-click contact (mailto / tel / copy)  
---

## Admin UX v1 — Shipped (2026-01-26)

- [x] Search input inside `/admin/requests` filters  
- [x] Case-insensitive search  
- [x] Highlight matches in list (name/title)  
- [x] Smart empty state with "Try archived?" CTA  
- [x] Dark-mode polish (admin)  
- [x] Navbar fixes (Profile + Logout POST/GET fallback)  
- [x] Tombstone delete (guarded)  
- [x] Archive / Unarchive UX  
- [x] Request notes (`admin_request_add_note` endpoint)  
- [x] Prevent 500 on request details (route exists + `url_for` fix)

## Admin UX v2 — Gmail-style (In Progress)

- [x] Live search (debounced)  
- [x] Disable auto-refresh on filters  
- [ ] Scroll restore after actions  
- [ ] Bulk actions (current page): Archive / Unarchive / Delete  
- [ ] Select-all (current page only)  
- [ ] Mini dashboard counters  
- [ ] Better empty states (no-results, no-live, no-archived)  
- [ ] Keyboard shortcuts (J/K, Esc, / to focus search)

---

## PHASE 3 – Public MVP

- [ ] Submit request form – polished UX  
- [ ] Success screen  
- [ ] Email notification to admin  
- [ ] Email confirmation to requester  
- [ ] Multilingual (BG / FR / EN)  
- [ ] Light anti-spam (honeypot or simple captcha)  

---

## PHASE 4 – Monetization (Soft)

- [ ] Pricing page  
- [ ] Pro signup form  
- [ ] Free vs Pro limits  
- [ ] Stripe integration (later)  

---

## PHASE 5 – Automation & AI

- [ ] StellaAI assistant  
- [ ] Auto-tagging of requests  
- [ ] Auto-assign by location  
- [ ] Auto-translation  

---

## WORK RULES (NON-NEGOTIABLE)

1. One session = one task only  
2. No new ideas before finishing the current phase  
3. Always commit after finishing a task  
4. Always update LAST STATE  
5. If a task takes more than 90 minutes → split it  

---

## LAST STATE

- Updated: 2026-01-25  
- DB: Added `Request.is_archived`, `Request.archived_at`, `Request.deleted_at` + indexes; Alembic head `fb611ecf034d` with AdminLog entity/created_at cols  
- Admin: Archive/unarchive flows fully wired (list + details + audit log); hidden archived requests by default; bulk actions + CSRF-safe POSTs shipped  
- KPI: `/pilot`, `/api/pilot/metrics`, `/api/pilot-kpi` ignore deleted requests (`deleted_at IS NULL`)
- UI: Global navbar search removed for MVP clarity; admin list search controls handle scoped queries
Next: Submit request UX polish OR admin pro features (bulk assign / SLA)

## 2026-01-25 — Admin UX v1 shipped

- Archive / Unarchive / Delete workflow completed (list + details + audit)
- Search by name/title added (case-insensitive + highlight)
- Smart empty state for zero results (suggest archived)
- Bulk select (current page only)
- Navbar fixes (logout POST+GET fallback, profile link)
- UI polish (badges, timestamps, dark-highlighted matches)
