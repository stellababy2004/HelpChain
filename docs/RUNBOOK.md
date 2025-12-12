# Runbook — Downloading and Verifying gitleaks SARIF

Quick steps to reproduce verification locally.

1) List recent workflow runs for `prebuild-and-deploy.yml` and find a successful run id:

```powershell
gh run list --repo stellababy2004/HelpChain.bg --workflow prebuild-and-deploy.yml --limit 20
```

2) Download artifacts for a specific run (replace `<RUN_ID>`):

```powershell
gh run download <RUN_ID> --repo stellababy2004/HelpChain.bg --dir artifacts
```

3) Locate SARIF and run local parser (we include `scripts/parse_gitleaks_sarif.py`):

```powershell
Get-ChildItem -Path artifacts -Recurse -Filter *.sarif -File
python .\scripts\parse_gitleaks_sarif.py .\artifacts\path\to\results.sarif
```

4) If the SARIF shows findings, download and inspect the detailed `results.sarif` JSON, map ruleId → file locations and triage.

Notes
-----
- Do not re-upload artifacts to public locations. Keep copies local and treat them as potentially sensitive until verified.
- If you must redact further, create a redaction commit and re-run CI.
