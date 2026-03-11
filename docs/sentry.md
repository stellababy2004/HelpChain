# Sentry Error Capture (Optional)

HelpChain supports optional Sentry integration for backend runtime exception capture.

## Required environment variable

- `SENTRY_DSN` : enables Sentry when present.

## Optional environment variables

- `SENTRY_ENVIRONMENT` : environment label shown in Sentry (`dev`, `staging`, `production`, etc.).
- `SENTRY_RELEASE` : release/version identifier.
- `SENTRY_TRACES_SAMPLE_RATE` : float (`0.0` to `1.0`) for performance traces. Default is `0.0`.

## Local enable example

```bash
set SENTRY_DSN=https://<key>@o0.ingest.sentry.io/<project>
set SENTRY_ENVIRONMENT=development
python run.py
```

If `SENTRY_DSN` is missing, Sentry remains disabled (no-op) and app startup behavior is unchanged.
