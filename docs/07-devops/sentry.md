# Sentry Integration

HelpChain supports optional Sentry integration for backend exception capture.

## Required Variable

- `SENTRY_DSN` enables Sentry when present.

## Optional Variables

- `SENTRY_ENVIRONMENT` labels the runtime environment.
- `SENTRY_RELEASE` identifies the deployed release.
- `SENTRY_TRACES_SAMPLE_RATE` controls tracing volume and defaults to `0.0` unless configured.

## Example

```powershell
$env:SENTRY_DSN="https://<key>@o0.ingest.sentry.io/<project>"
$env:SENTRY_ENVIRONMENT="development"
python run.py
```

If `SENTRY_DSN` is not set, the application should continue to start without Sentry.
