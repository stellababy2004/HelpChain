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
