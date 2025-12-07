# December 5–15 Ramp-up Plan — Day-by-day

Цел: Завършване на критичните елементи (2FA, секрети, CI/CD, AI интеграция, UI фиксове, тестове и подготовка за публичен launch) до и включително 15 декември 2025.

Кратко резюме: планът е оптимизиран за малък екип (1-3 разработчика + 1 QA/DevOps), при наличие на тестова и staging среда.

Общо време: 9–11 работни дни (5–15 декември). Всяка задача има приблизителен времеви ангажимент.

Legend:
- Owner: suggested role (Backend/DevOps/Frontend/QA/Docs)
- Est: est. hours

---

Day 1 — 2025-12-05 (днес)
- Owner: Backend
- Tasks:
  - Finalize and merge minimal 2FA fixes PR (session key unification, commits on enable/disable, login redirect). Est: 3h
  - Add `docs/admin_2fa_README.md` and share with team. Est: 1h
  - Quick smoke test in local test env / run `pytest -k admin` (fix any immediate breakages). Est: 2h

Day 2 — 2025-12-06
- Owner: Backend + QA
- Tasks:
  - Harden login flow: ensure email-2fa and totp-2fa flows do not conflict. Est: 3h
  - Add/adjust unit tests and integration tests (edge cases: expired TOTP, replay tokens). Est: 3h
  - QA runs tests in staging. Est: 2h

Day 3 — 2025-12-07
- Owner: DevOps + Backend
- Tasks:
  - Secrets plan: choose solution (GitHub Secrets + Vault roadmap or `sops` for repo encryption). Est: 2h
  - Implement short-term encrypted `.env` approach or document steps for Vault integration. Est: 4h
  - Update CI to read secrets from chosen mechanism for staging. Est: 2h

Day 4 — 2025-12-08
- Owner: Backend + Frontend
- Tasks:
  - UX polish for 2FA setup pages: show QR, copy secret, instructions for authenticator apps. Est: 4h
  - Add recovery codes generator stub (store/display) — implementation minimal. Est: 3h

Day 5 — 2025-12-09
- Owner: Backend + QA
- Tasks:
  - End-to-end tests: login→2FA→dashboard for multiple browsers/clients. Est: 4h
  - Fix any bugs found. Est: 2–3h

Day 6 — 2025-12-10
- Owner: Backend + DevOps
- Tasks:
  - CI/CD: add pipeline stage for deploying to staging and running smoke tests. Est: 4h
  - Run full test suite in CI (resolve failures unrelated to 2FA as time permits). Est: 3h

Day 7 — 2025-12-11
- Owner: AI Team + Backend
- Tasks:
  - Finalize AI integration (provider config, model endpoint, fallback). Est: 6h
  - Run AI load/self-test on staging. Est: 2h

Day 8 — 2025-12-12
- Owner: Frontend + QA
- Tasks:
  - UI/UX fixes for admin and volunteer dashboards (responsive checks ≤375px). Est: 6h
  - Accessibility quick audit for admin flows. Est: 2h

Day 9 — 2025-12-13
- Owner: QA + Backend
- Tasks:
  - Security review: confirm 2FA persistence, secrets not in logs, session keys rotated where necessary. Est: 4h
  - Run penetration quick-check (simple auth brute-force tests, confirm rate-limiting/locks if implemented). Est: 3h

Day 10 — 2025-12-14
- Owner: Marketing + Project Lead
- Tasks:
  - Prepare launch material: release notes, changelog (`docs/changes.md`), social copy. Est: 4h
  - Prepare rollback plan and post-deploy checklist. Est: 2h

Day 11 — 2025-12-15
- Owner: All (release day rehearsal)
- Tasks:
  - Final staging deploy and smoke tests. Est: 2–3h
  - Code freeze + final sign-offs (security, QA, product). Est: 2h
  - If all green — deploy to production (or schedule exact deploy window). Est: 1–2h

---

Notes & Recommendations

- Triage: keep a daily 30–45 minute sync (standup) to unblock cross-team dependencies.
- Scope control: if AI integration slips, prioritize security and CI/CD first — you can delay public AI features but not core security.
- Parallelization: secrets work and UI fixes can run in parallel across 2 engineers.
- Testing: reserve time for fixing flaky tests discovered in CI; test flakiness is typical when integrating session changes.

If тази схема изглежда добре, мога:
- да създам GitHub PR с документацията и PR description, и
- да добавя задачите в issues (one issue per day or per deliverable) или в project board, за да проследим статуса.
