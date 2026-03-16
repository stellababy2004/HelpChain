# HelpChain Intervenant Migration Plan

## 1. Current State
- The canonical data model is documented in `docs/architecture/data-model.md`.
- `/admin/intervenants` is the canonical UI entrypoint.
- `/admin/volunteers` remains as a legacy compatibility alias.
- UI terminology is already “Intervenants”.
- The underlying data still comes from the legacy `Volunteer` model.
- No schema refactor has occurred yet.
- Tenant scoping, admin workspace layout, audit trail, and role separation already exist.

## 2. Target State
- **Intervenant** becomes the canonical actor model.
- `actor_type` values represent operational reality:
  - `volunteer`, `professional`, `association`, `municipal_service`, `social_worker`.
- **Assignment** becomes a first‑class relation between `Request` and `Intervenant`.
- Volunteer is no longer a primary concept; it is only a subtype (`actor_type='volunteer'`).

## 3. Migration Risks
- Breaking current admin pages that still rely on the legacy `Volunteer` model.
- Losing or duplicating volunteer data during model transition.
- Route inconsistencies between `/admin/intervenants` and legacy endpoints.
- Mixing legacy semantics with canonical actor semantics in UI and code.
- Tenant scoping mistakes when new models are introduced.

## 4. Proposed Migration Phases

### Phase A — Conceptual/UI Alignment (Done)
- **Objective:** UI and navigation use “Intervenants” terminology.
- **Involved:** templates, navigation, labels.
- **Migration:** None.
- **Impact:** No data changes.
- **Rollback:** Trivial (labels only).

### Phase B — Route Truth Cleanup (Mostly Done)
- **Objective:** `/admin/intervenants` becomes canonical; `/admin/volunteers` is legacy alias.
- **Involved:** admin routes, templates, navigation.
- **Migration:** None.
- **Impact:** Minimal route changes only.
- **Rollback:** Low (aliases can be restored).

### Phase C — Introduce Intervenant Model (Future)
- **Objective:** Add `Intervenant` model (canonical actor entity).
- **Involved:** `models.py`, migrations, admin routes, templates.
- **Migration:** New schema + initial data backfill.
- **Impact:** Moderate (dual read or cutover needed).
- **Rollback:** Medium (schema rollback + dual‑write cleanup).

### Phase D — Add Assignment Model (Future)
- **Objective:** Create explicit `Assignment` between `Request` and `Intervenant`.
- **Involved:** models, migrations, request workflows, admin UI.
- **Migration:** New schema + optional data backfill from legacy ownership.
- **Impact:** Medium‑high (touches request workflows).
- **Rollback:** Medium (requires mapping back to legacy owner field).

### Phase E — Migrate Legacy Volunteer Screens (Future)
- **Objective:** Replace volunteer‑backed pages with Intervenant data.
- **Involved:** `/admin/intervenants`, detail pages, filters, exports.
- **Migration:** Data mapping + UI updates.
- **Impact:** Medium (UI and queries switch source model).
- **Rollback:** Medium (switch back to legacy model).

### Phase F — Decommission Legacy Volunteer Semantics (Future)
- **Objective:** Remove `/admin/volunteers` and volunteer‑centric naming.
- **Involved:** routes, templates, docs.
- **Migration:** None (deprecate + remove).
- **Impact:** Low‑medium (breaking change for legacy links).
- **Rollback:** Low (restore alias route).

## 5. Phase Details (Per Phase)
Each phase should be delivered independently with:
- **Objective** clearly scoped.
- **Files/Models/Routes** explicitly listed in implementation plan.
- **Migration need** stated (Yes/No).
- **Expected impact** (UI only / schema + code / workflows).
- **Rollback complexity** (Low / Medium / High).

## 6. Data Transition Strategy
Legacy `Volunteer` rows should map to:
- `Intervenant(actor_type='volunteer')`
- Preserve key fields: `name`, `email`, `phone`, `location`, `is_active`, `created_at`.
- Keep legacy IDs accessible in a temporary mapping table or a `legacy_volunteer_id` field (if needed in Phase C/D).

## 7. Request Ownership vs Assignment Strategy
- **Current:** `owner_id` / `assigned_to_user_id` indicates the internal operational owner.
- **Target:** `Assignment` captures a broader set of actor relationships and history.
  - `owner_id` can remain the operational “current owner”.
  - `Assignment` records all intervenant links, timing, and actions.

## 8. Recommended Implementation Order
1. Complete Phase B (route truth, UI labels) — already mostly done.
2. Add Intervenant model (Phase C) with minimal schema and no UI cutover yet.
3. Add Assignment model (Phase D).
4. Switch admin pages to Intervenant data source (Phase E).
5. Remove legacy routes/labels (Phase F).

## 9. Phase 1 Recommendation (What to Do Next)
**Next practical step:** start Phase C with the minimal Intervenant model and **no UI cutover** yet.

**Explicitly wait on:**
- Assignment model (Phase D) until Intervenant is stable.
- UI/data source switch (Phase E) until data migration plan is validated.
- Removing `/admin/volunteers` (Phase F) until all references are clean.
