Subject: [Security] Incident report — potential artifact secret exposure (2025-12-12)

Summary:
- On 2025-12-12, a CI prebuild artifact produced by `npx vercel build` contained files that were flagged by a secrets scanner.
- Immediate remediation was performed (tokens rotated, artifacts removed where public).
- CI was hardened to scan prebuilt output with `gitleaks`; verification run completed with no findings.

Impact:
- No evidence of production compromise.
- Tokens identified were rotated/revoked.

Actions taken:
- Redaction commits applied to repository for any test secrets.
- `.gitleaks.toml` and workflow updated to scan a sanitized copy of `.vercel/output`.
- CI run `20165870895` produced `results.sarif` and gitleaks reported 0 findings after fixes.

Recommended follow-up:
- Review `docs/INCIDENT-2025-12-12.md` and `docs/RUNBOOK.md` for details and verification steps.
- If you have questions or see unexplained activity, contact the repository owner.

Prepared by: repository owner
