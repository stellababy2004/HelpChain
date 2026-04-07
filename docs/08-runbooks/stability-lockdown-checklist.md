# Stability Lockdown Checklist

Use this checklist during a stabilization window when the operational priority is reliability rather than feature work.

## Rules for the Session

- Do not introduce unrelated features.
- Do not redesign active screens during a stability pass.
- Prefer diagnose, fix, verify, and lock over exploratory changes.

## Operator Checklist

- [ ] Reproduce the issue in a controlled environment.
- [ ] Identify whether the Request workflow is affected.
- [ ] Apply the smallest safe fix.
- [ ] Verify `/health` and the relevant smoke path.
- [ ] Confirm no permission or tenant-scoping regression was introduced.
- [ ] Capture follow-up work separately if broader cleanup is still needed.
