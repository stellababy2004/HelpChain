# Visual Regression Baseline (Public Institutional Pages)

This project uses a lightweight Playwright screenshot flow for public UI regression checks.

## Covered Pages

Desktop baseline covers:

- `/`
- `/comment-ca-marche`
- `/collectivites-associations`
- `/cas-usage`
- `/partenariats`
- `/pilotage-indicateurs`
- `/professionnels`
- `/securite`
- `/architecture`
- `/gouvernance`
- `/faq`
- `/mentions-legales`
- `/confidentialite`
- `/conditions-utilisation`

Mobile baseline (`390x844`) covers the highest-value pages:

- `/`
- `/comment-ca-marche`
- `/collectivites-associations`
- `/professionnels`
- `/securite`
- `/architecture`
- `/gouvernance`
- `/faq`
- `/mentions-legales`
- `/confidentialite`
- `/conditions-utilisation`

## File Locations

- Baselines: `tests/visual/baseline/desktop/` and `tests/visual/baseline/mobile/`
- Current run captures: `tests/visual/current/desktop/` and `tests/visual/current/mobile/`
- Diff images: `tests/visual/diff/desktop/` and `tests/visual/diff/mobile/`
- Compare report: `tests/visual/last-compare-report.json`

## How to Run

1. Start the local app (example):

```powershell
c:\dev\HelpChain.bg\.venv\Scripts\python.exe run.py
```

2. Generate/update baseline screenshots:

```powershell
c:\dev\HelpChain.bg\.venv\Scripts\python.exe scripts\visual_baseline_playwright.py --mode baseline --base-url http://127.0.0.1:5000
```

3. Capture a current run and compare against baseline:

```powershell
c:\dev\HelpChain.bg\.venv\Scripts\python.exe scripts\visual_baseline_playwright.py --mode compare --base-url http://127.0.0.1:5000
```

## Diff Review Workflow

1. Open `tests/visual/last-compare-report.json`.
2. Check entries with `"status": "changed"`.
3. Open corresponding files under `tests/visual/diff/...`.
4. Validate institutional intro consistency, homepage structure, footer stability, spacing/typography rhythm, and overflow issues before accepting changes.

