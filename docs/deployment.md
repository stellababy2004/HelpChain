# Routing & Deployment Policy

> Source of truth: see vercel.json in the repository root.

**Routing policy (canonical):**

- explicit-only endpoints
- 404 by default
- контролирано добавяне на нови маршрути
- детерминирано поведение (без ghost bugs)

**Препоръка за употреба:**
- Остави този текст във vercel.json като коментар (source of truth).
- Копирай 1:1 в README.md или docs/deployment.md под секция “Routing & Deployment Policy”.
- Ако имаш PR – сложи го и в PR description (като context, не като шум).

**Checklist за стабилност:**
- /api/_health → 200
- /health → 200
- unknown route → 404

**Твърдо мнение:**
Преместваме “поведение” от имплицитно към договорно. Това е разликата между “работи сега” и “работи след 6 месеца без драма”.
