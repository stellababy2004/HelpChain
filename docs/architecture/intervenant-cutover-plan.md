# HelpChain Intervenant Cutover Plan (Phase E)

## 1. Current UI/Data Source State
- `/admin/intervenants` and its detail page are **Volunteer-backed**.
- UI terminology is already “Intervenants”.
- `/admin/volunteers` remains as a legacy alias route.
- No admin UI reads from `Intervenant` yet.
- `Assignment` exists but is not used in UI or workflows.

## 2. Cutover Target
- `/admin/intervenants` list reads from **Intervenant**.
- Intervenant detail page reads from **Intervenant**.
- Assignment is introduced only where it clarifies **actor‑request relationships** (not as a replacement for `owner_id` yet).

## 3. Dependencies (Pre‑Cutover)
- Migrations applied:
  - `intervenants` table
  - `assignments` table
  - `legacy_volunteer_id` on `intervenants`
  - `structure_id` on `assignments`
- Backfill scripts available:
  - Volunteers → Intervenants
  - Requests → Assignments (partial, volunteer‑based)
- Validation checks complete:
  - Intervenants populated
  - `legacy_volunteer_id` correctly set
  - structure consistency verified

## 4. Cutover Phases

### Phase E1 — Read‑only switch for `/admin/intervenants` list
**Objective**
- List page reads from `Intervenant` only.

**Likely files**
- `backend/helpchain_backend/src/routes/admin.py`
- `templates/admin_volunteers.html`

**Risks**
- Empty list due to missing backfill
- Missing fields (email/phone/location) if not populated

**Rollback difficulty**
- Low (switch query back to `Volunteer`)

**Validation**
- Counts match `Volunteer` totals per structure
- Spot‑check 5–10 rows

---

### Phase E2 — Detail page switch
**Objective**
- Detail page reads from `Intervenant`.

**Likely files**
- `backend/helpchain_backend/src/routes/admin.py`
- `templates/volunteer_detail.html`

**Risks**
- Missing actor record due to mapping gaps

**Rollback difficulty**
- Low

**Validation**
- Direct link from list → detail works
- Data fields display as expected

---

### Phase E3 — Optional enrichments (safe, non‑breaking)
**Objective**
- Show `actor_type` and structure context in the list/filter.

**Likely files**
- `templates/admin_volunteers.html`
- (optional) admin filters in `admin.py`

**Risks**
- None if purely display

**Rollback difficulty**
- Trivial

**Validation**
- Verify filter works on actor_type

---

### Phase E4 — Controlled use of Assignment in UI
**Objective**
- Surface simple assignment indicators (count or latest assignment) on detail page.

**Likely files**
- `admin.py` (queries)
- `templates/volunteer_detail.html`

**Risks**
- Incomplete backfill may show missing data

**Rollback difficulty**
- Low

**Validation**
- Assignment count matches expected on sample requests

---

### Phase E5 — Deprecation of Volunteer‑backed admin reads
**Objective**
- Stop reading volunteers in admin actor management
- Keep `/admin/volunteers` as a legacy alias until removed

**Likely files**
- `admin.py` routes

**Risks**
- Legacy tools expecting Volunteer data may break

**Rollback difficulty**
- Medium (requires re‑enabling Volunteer query paths)

**Validation**
- All Intervenant pages work without Volunteer reads

## 5. Data Validation Strategy
**Before cutover**
- `Volunteer.count == Intervenant.count` per structure
- Check % missing `legacy_volunteer_id`
- Sample verify: Volunteer(id=X) ↔ Intervenant(legacy_volunteer_id=X)

**After cutover**
- Lists show same count and fields
- Random spot checks on 10 records
- No structure mismatches

## 6. Rollback Strategy
- Each phase should be toggled by switching the query layer only.
- Keep Volunteer query path intact until Phase E5.
- If a step fails, revert to Volunteer‑backed queries without schema rollback.

## 7. Recommended Immediate Next Coding Step
**Phase E1 (read‑only list cutover)**:
- Swap the `/admin/intervenants` list query from `Volunteer` → `Intervenant`.
- Keep detail page Volunteer‑backed until E2.
- Add a fallback banner if the Intervenant table is empty.

---

## Biggest Cutover Risk
- **Incomplete or inconsistent backfill**, leading to empty lists or missing actor details. Use strict validation before switching UI reads.
