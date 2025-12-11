# December 5–15 Ramp-up Plan — Professional Release Readiness

Версия: 1.1 — обновено на 11 декември 2025

Цел
 - Осигуряване на стабилна, сигурна и тествана версия на HelpChain за публичен launch. Фокус през периода: 2FA стабилност, секрети/CI, AI интеграция, финални UI фиксове и тестове.

Кратко резюме
 - Планът е създаден за малък екип (1–3 разработчика + 1 QA/DevOps). Включва ясни deliverables, критерии за приемане и рискове.

Ключови deliverables
 - Сигурен и тестван 2FA поток (admin + user flows)
 - Сигурно управление на секрети и CI, работещ prebuilt Vercel pipeline
 - Работеща AI интеграция със fallback механизъм
 - UI/UX корекции и базова достъпност за админ/volunteer панели
 - Тестови suite: unit, integration и E2E проверки, smoke тестове в staging

Legend
 - Owner: препоръчана роля (Backend / DevOps / Frontend / QA / Docs)
 - Est: приблизително време (ч)

Приемни критерии (по задача)
 - 2FA: успешен е2е тест (login → 2FA → dashboard) в staging за 2 различни браузъра
 - CI/CD: prebuilt pipeline в Actions, `.vercel/output` артефакт и успешен `npx vercel deploy --prebuilt` в preview/стaging
 - AI: заявка към модел с fallback и наблюдавани успешни отговори за стандартни промптове
 - UI: критични UX проблеми затворени, основни aria-labels присъстват

Рискове и мерки за смекчаване
 - Забавяне в AI интеграцията → приоритизира се сигурността и CI; AI се пуска като частична/feature-flagged функционалност
 - Flaky тестове в CI → отделяне на време за стабилизиране (паралелно с fixes)
 - Secrets leak: използване на GitHub Secrets за production, временен `sops`/encrypted .env за dev/staging

---

## План (ден по ден)

Day 1 — 2025-12-05 (Owner: Backend)
 - Tasks:
   - Finalize and merge minimal 2FA fixes PR (session key unification, enable/disable flows, login redirect). Est: 3h
   - Add `docs/admin_2fa_README.md` with setup + troubleshooting. Est: 1h
   - Quick smoke test locally / run `pytest -k admin`. Est: 2h
 - Acceptance: PR merged, smoke tests green locally

Day 2 — 2025-12-06 (Owner: Backend + QA)
 - Tasks:
   - Harden login flow and reconcile email-2fa and totp-2fa branches. Est: 3h
   - Add/adjust unit & integration tests (expired TOTP, replay, edge cases). Est: 3h
   - QA runs test cases in staging. Est: 2h
 - Acceptance: automated tests added + passing in CI or documented failures tracked as issues

Day 3 — 2025-12-07 (Owner: DevOps + Backend)
 - Tasks:
   - Define secrets strategy (GitHub Secrets + Vault plan or `sops`). Est: 2h
   - Implement short-term encrypted `.env` or document Vault steps. Est: 4h
   - Update CI to consume chosen secret mechanism for staging. Est: 2h
 - Acceptance: secrets consumed in staging pipeline; no plaintext secrets in repo

Day 4 — 2025-12-08 (Owner: Backend + Frontend)
 - Tasks:
   - UX polish for 2FA setup (QR, copy secret, instructions). Est: 4h
   - Add recovery codes generation + display/store stub. Est: 3h
 - Acceptance: 2FA setup UI available and manual test passes

Day 5 — 2025-12-09 (Owner: Backend + QA)
 - Tasks:
   - E2E tests: login→2FA→dashboard on multiple browsers. Est: 4h
   - Triage and fix critical bugs. Est: 2–3h
 - Acceptance: E2E green or documented failures with issues assigned

Day 6 — 2025-12-10 (Owner: Backend + DevOps) — COMPLETED
 - Tasks:
   - CI/CD: add prebuilt pipeline (GitHub Actions + Vercel prebuilt) and size checks. Est: 4h
   - Run full test suite in CI and address blocking failures. Est: 3h
 - Status: ✅ Done — pipeline added and prebuild diagnostics available

Day 7 — 2025-12-11 (Owner: AI Team + Backend)
 - Tasks:
   - Finalize AI provider configuration, endpoint, and fallback logic. Est: 6h
   - Run AI load/self-test on staging (basic throughput & correctness). Est: 2h
 - Acceptance: AI service responds to canonical prompts and fallback triggers when needed

Day 8 — 2025-12-12 (Owner: Frontend + QA)
 - Tasks:
   - UI/UX fixes for admin and volunteer dashboards (responsive ≤375px). Est: 6h
   - Accessibility quick audit (key admin flows). Est: 2h
 - Acceptance: Critical responsive issues fixed; accessibility blockers documented/resolved

Day 9 — 2025-12-13 (Owner: QA + Backend)
 - Tasks:
   - Security review: confirm 2FA persistence, remove secrets from logs, verify session key rotation. Est: 4h
   - Run light penetration checks (auth brute-force, rate-limiting). Est: 3h
 - Acceptance: No high-severity findings; open items tracked

Day 10 — 2025-12-14 (Owner: Marketing + Project Lead)
 - Tasks:
   - Prepare release notes, changelog (`docs/changes.md`) and announcement copy. Est: 4h
   - Finalize rollback plan and post-deploy checklist. Est: 2h
 - Acceptance: Release assets ready and reviewed

Day 11 — 2025-12-15 (Owner: All)
 - Tasks:
   - Final staging deploy + smoke tests. Est: 2–3h
   - Code freeze and sign-offs (security, QA, product). Est: 2h
   - Production deploy (if green) or schedule window. Est: 1–2h
 - Acceptance: Production deploy succeeded or rollback plan ready

---

Communication & Rituals
 - Daily short sync (20–30 min) — recommended: 09:30 CET (adjust if needed)
 - Use Issues for task tracking; label with `release/dec-2025` and owners
 - Post daily status in the `#release` channel with 3 lines: Done / In progress / Blockers

Action items to finalize plan
 - Create PR `docs/DECEMBER_RAMPUP_PLAN.md` with this updated plan (title: "Release ramp-up: Dec 5–15 — finalized plan")
 - Create issues for each day/deliverable (template included below)
 - Assign owners and estimate times in GitHub issues

Issue template (use for each deliverable)
 - Title: [Day X] Short deliverable title
 - Body:
   - Owner: @username
   - Description: Clear task description and acceptance criteria
   - Est: Xh
   - Dependencies: (other issues / secrets / infra)

Contacts
 - Release lead: @project-lead (assign real GitHub username)
 - DevOps: @devops
 - QA: @qa

Next steps (recommended)
 1. Create PR with this file and request review from Release lead + DevOps (auto-merge after approvals).
 2. Create GitHub issues for Day 7–11 and assign owners.
 3. Schedule daily standups in calendar and pin the channel for release updates.

---

If искате, мога да създам PR и отделни GitHub issues за всяка задача/ден — кажете кои да създам автоматично и с какви assignees.
