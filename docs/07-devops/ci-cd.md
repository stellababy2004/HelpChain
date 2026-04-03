# CI/CD Policy

HelpChain uses a blocking CI/CD pipeline intended to prevent schema drift, unstable runtime behavior, and unsafe deployments.

## Mandatory CI Stages

1. Initialize the test database.
2. Run schema-drift checks between ORM expectations and the actual database.
3. Run smoke coverage for core CRUD and runtime paths.
4. Run automated tests.

Any failed stage blocks the pipeline.

## Policy Rationale

- Prevent silent divergence between models and runtime storage.
- Preserve reproducible environments across development and deployment.
- Reduce operational risk for an institutional production context.
