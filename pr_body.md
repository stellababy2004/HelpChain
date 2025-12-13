Summary:
Stabilizes legacy admin/volunteer test flows by binding module session and adding opt-in flags.

What changed:
- Fixes for session binding affecting admin flows
- Test shims guarded behind opt-in flags: HELPCHAIN_ALLOW_MODULE_ENGINE, HELPCHAIN_LEGACY_ADMIN_ALIAS

Local verification:
- Removed corrupted backend/test_local.sqlite and ran backend subset tests with opt-in flags
- Result: 57 passed, 28 deselected, 23 warnings

Notes for reviewers:
- Local tests were executed with (PowerShell):

```powershell
$env:HELPCHAIN_ALLOW_MODULE_ENGINE='1'; $env:HELPCHAIN_LEGACY_ADMIN_ALIAS='1'; pytest backend -k "admin or volunteer" -q
```

- These flags are opt-in and do not change production behavior when unset.

Checklist (please verify in CI / review):
- [ ] Run full CI (all tests)
- [ ] Security scan / secret-scan
- [ ] Linting and formatting checks
- [ ] Verify DB migrations (if any)
- [ ] Manual admin flows smoke test (login, 2FA where applicable)
- [ ] Update docs/changes.md if merge included changes

If gh cannot complete creation in this environment, please create a PR manually using the above title/body.
