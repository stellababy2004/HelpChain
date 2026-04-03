# Visual Regression Baseline

HelpChain uses a lightweight Playwright-based screenshot flow for public UI regression checks.

## Coverage

Desktop coverage includes the main institutional and public information pages. Mobile coverage focuses on the highest-value public routes.

## Artifact Locations

- Baselines: `tests/visual/baseline/`
- Current captures: `tests/visual/current/`
- Diffs: `tests/visual/diff/`
- Compare report: `tests/visual/last-compare-report.json`

## Typical Usage

1. Start the local application.
2. Generate or update baselines with the visual regression script.
3. Run compare mode against the same base URL.
4. Review diff artifacts before accepting UI changes.

## Review Focus

When reviewing diffs, confirm:

- layout stability
- typography and spacing consistency
- footer and navigation consistency
- overflow or clipping regressions
- unintended changes on key public pages
