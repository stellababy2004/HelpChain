# Local Development

## Status
- Reviewed: 2026-04
- Status: Active
- Source of truth: Partial
- Review required: Yes
- Notes: Validate against the current developer tooling and local wrapper scripts before relying on this document as the only setup reference.

## Purpose

This document defines the expected local development workflow for HelpChain. It consolidates local startup, runtime, and helper-command guidance into one stable reference.

## Environment Expectations

- Python is required for the Flask application and local scripts.
- The local application entry point is expected to be the Flask app exposed as `backend.appy:app`.
- SQLite is the current expected local database unless an explicit alternative is configured for a controlled task.
- The repository wrapper script `scripts/dev.ps1` is the preferred entry point for routine local workflows when available.

## Canonical Local Startup

Current expected workflow:

1. Run `powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 bootstrap`
2. Run `powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 run`

Fallback direct workflow:

1. Run `python backend/scripts/dev_reset.py`
2. Run `python backend/scripts/system_health.py`
3. Run `flask --app backend.appy:app run`

## Common Commands

Use the unified wrapper:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 <command>
```

Common commands:

- `help` to list available local commands
- `bootstrap` to prepare the local environment
- `run` to start the local server
- `doctor` to inspect runtime and database configuration
- `smoke` to run smoke checks
- `go-no-go` to perform a quick readiness check
- `scan-secrets` to run a manual secret scan

## Sanity Checks

Run these after local startup:

- `python backend/scripts/system_health.py`
- `powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 doctor`
- `powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 smoke`

Typical routes to verify locally:

- `/`
- `/submit_request`
- `/admin/login`
- `/health`

## Runtime Notes

- Historical machine-specific interpreter paths and local database paths existed in older notes. They are not the source of truth for active documentation.
- If a task requires an explicit `DATABASE_URL`, verify the local target before running migrations or write-oriented scripts.
- If startup succeeds but admin or request flows fail, run the doctor and smoke commands before changing configuration.
