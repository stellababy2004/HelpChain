# Secret Safety (Local)

## Rule
- Do not commit secrets (passwords, API keys, tokens, access keys).
- Keep credentials in environment variables.

## Local guard
- A local pre-commit hook scans staged files for likely secrets.
- If a possible secret is detected, commit is blocked.

Block message:
- `SECRET GUARD: possible credential detected in staged files`
- `Remove the secret or move it to environment variables before commit.`

## Manual scan
- Full tracked files scan:
  - `powershell -ExecutionPolicy Bypass -File .\scripts\scan_secrets.ps1`
- Staged files only:
  - `powershell -ExecutionPolicy Bypass -File .\scripts\scan_secrets.ps1 -StagedOnly`

## Notes
- Placeholder values like `your_password_here`, `example`, `changeme`, `dummy` are ignored when clearly fake.
- If uncertain, prefer removing the value from code and using env vars.

## GitHub Secret Scanning
- GitHub Actions runs a repository secret scan on every `push` and `pull_request`.
- Workflow file: `.github/workflows/secret-scan.yml`.
- Scanner config: `.gitleaks.toml`.
- If a possible secret is detected, the workflow fails.
- Move credentials to environment variables before pushing changes.
