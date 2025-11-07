CI run without tracing — 2025-11-07

- Action: Ran pytest in production-like mode with tracing/debug disabled.
  - Command used: `HELPCHAIN_TEST_DEBUG=0 HELPCHAIN_TEST_TRACEMALLOC=0 pytest -q -W ignore` (PowerShell: set environment variables then run pytest)
  - Result: 13 passed, 0 failed
  - Warnings: none significant (external DeprecationWarnings may be ignored)

- Notes: Session-level seed and teardown behaved correctly in this run. CI run without tracing is ready for automation in GitHub Actions.
