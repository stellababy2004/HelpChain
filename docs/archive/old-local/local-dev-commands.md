# Local Dev Commands

Use the unified local wrapper:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 <command>
```

Common commands:

- `help` - show all commands
- `bootstrap` - local bootstrap flow
- `run` - start local server
- `doctor` - runtime/database diagnostics
- `smoke` - smoke test suite
- `go-no-go` - readiness check
- `scan-secrets` - manual secret scan

Canonical local flow:

1. `bootstrap`
2. `run`
3. `doctor`
4. `smoke`
