# Deploy readiness boundary

`scripts/deploy_readiness.py` is a read-only release check. It verifies that
the exact current Git commit has a completed, successful run of
`.github/workflows/quality-gate-full.yml` in GitHub Actions. It does not accept a
local run or FAST mode, does not use production secrets, and never calls Render.

Run locally with an authenticated GitHub CLI session:

```powershell
gh auth status
& ".\.venv\Scripts\python.exe" scripts/deploy_readiness.py
```

If GitHub CLI is unauthenticated, the commit has no run, or the run is queued,
in progress, failed, or cancelled, the command returns a non-zero exit code.

This is not a technical lock on a user clicking Deploy in the Render dashboard.
The durable protection is repository policy: require the `Quality Gate / Final`
job as a required GitHub status check and permit production deployment only
from the protected default branch after that check succeeds. Render auto-deploy
and manual dashboard permissions must be configured separately by an owner.
