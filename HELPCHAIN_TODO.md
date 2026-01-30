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

## PHASE 2 – Admin UX

- [ ] Status filters (Pending / In progress / Done)  
- [ ] Search by name / title  
- [ ] Mini dashboard counters  
- [ ] Bulk archive action  
- [ ] Better empty states  

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

- Updated: 2026-01-24  
- DB: Added `Request.is_archived`, `Request.archived_at`, `Request.deleted_at` + indexes; Alembic head `9c6b7a2b0a77`  
- Admin: Archive/unarchive + Deleted/restore-deleted flows; admin request list filters include `archived` and `deleted`  
- KPI: `/pilot`, `/api/pilot/metrics`, `/api/pilot-kpi` ignore deleted requests (`deleted_at IS NULL`)  

## Volunteer Area — MVP (in progress)

### ✅ Done (2026-01-29)
- Session-based volunteer login (email-only, no password)
- Volunteer login flow: `/volunteer_login` → `/volunteer/dashboard`
- Volunteer logout (POST-only, clears session)
- Admin login fully removed from public UI
- Fixed volunteer routes:
  - Dashboard: `/volunteer/dashboard`
  - Profile: `/volunteer/profile`
- Navbar adapts to volunteer session (Dashboard / Profile / Logout)
- Volunteer dashboard CTA aligned: “Направи профила си готов за свързване”
- Matching v1 adapted to model without `is_remote`
- Seed volunteer + seed request working

### 🚧 In progress
- Volunteer dashboard UX (human, not empty)
- Volunteer profile UX redesign (hc-* design system)

### Volunteer Dashboard — UX polish (IN PROGRESS)
- [x] Clear primary CTA: “Направи профила си готов за свързване”
- [x] Preview state when request arrives (highlight + NEW)
- [ ] Activity & urgency micro-copy under last activity
- [ ] Animated / highlighted match card on new request
- [ ] Stronger guidance toward profile completion

### Volunteer Profile — UX & conversion (NEXT)
- [ ] Reduce friction (chips, presets, examples)
- [ ] Clear “profile ready” end-state
- [ ] Explain matching in human language (no tech)

### ⏭️ Next (tomorrow)
- Finish Volunteer Dashboard:
  - Add activity / social proof block
  - Add “what happens when a request arrives” preview state
- Finalize Volunteer Profile form → backend field mapping
- Replace temporary empty states with human copy
