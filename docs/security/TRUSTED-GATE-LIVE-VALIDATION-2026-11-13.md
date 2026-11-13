# Trusted Security Gate — live validation (2026-11-13)

This documentation-only change is a controlled smoke test of the trusted security evaluator after merging PR #216.

Validation criteria:
- The PR's CodeQL, Trivy, Bandit/pip-audit, and Secret Scan workflows complete.
- The trusted `workflow_run` evaluator executes from the default branch.
- The evaluator resolves the PR head and scanned merge commit without mixing their SHAs.
- The evaluator validates the evidence and publishes a check on the exact PR head SHA.
- A successful result is accepted only if the real `Trusted security verdict` reports `PASS`; a green reporting workflow alone is insufficient.

This test changes no application code, secrets, infrastructure, database, or deployment configuration. Do not merge this PR merely to run the test.
