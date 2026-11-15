# PR #229 — Owner review of admin client-IP fallback (Bandit B104)

## Decision (2026-11-15)

The repository owner explicitly approved the exact Bandit B104 finding `bandit|b104|backend/helpchain_backend/src/routes/admin.py|2423` as a **false positive for network binding**, subject to preserving source-context and severity checks. This decision is limited to this finding, not a blanket B104 exemption.

## Reviewed source and behavior

```python
def _client_ip() -> str:
    # ProxyFix normalizes remote_addr only when proxy trust is explicitly enabled.
    # Never read X-Forwarded-For directly: direct clients can forge it.
    # This keeps audit and lockout identity aligned with Flask-Limiter.
    return request.remote_addr or "0.0.0.0"
```

The fallback literal is returned as a client-IP identity string. This function does not open or bind a listening socket. Call sites include admin authentication attempts and lockout, MFA/audit metadata, and privileged administrative activity logging.

## Exact-match policy constraints

- Finding: `bandit|b104|backend/helpchain_backend/src/routes/admin.py|2423`
- Scanner / rule: Bandit / B104
- Expected severity: `unclassified`
- Context digest (from PR #211 evidence proposal; must match scanned source): `sha256:8168a08e75fe76475215886ac7447558e07540a82ea3226f89cb18373813f385`
- Expiration: 2027-11-15
- Prior evidence: `docs/security/PR-211-B104-DISPOSITION-PROPOSAL-2026-11-14.json`

## Residual risk and follow-up

If `request.remote_addr` is absent, multiple requests share the fallback identity `0.0.0.0`. This may reduce audit attribution and cause lockout identity collisions. Review separately; this owner decision does not assert that the fallback is ideal, nor does it disable scanning.
