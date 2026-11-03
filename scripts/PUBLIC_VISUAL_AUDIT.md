# Public visual audit

The audit uses the existing project virtual environment and Playwright's
Chromium browser. It only navigates public GET routes and performs safe UI
checks; it does not submit forms or modify the database.

Start the local Flask server first at `http://127.0.0.1:5000`, then run from
PowerShell:

```powershell
& ".\.venv\Scripts\python.exe" ".\scripts\public_visual_audit.py"
```

Optional base URL and output directory:

```powershell
& ".\.venv\Scripts\python.exe" ".\scripts\public_visual_audit.py" `
  --base-url "http://127.0.0.1:5000" `
  --output-dir ".\reports\visual-audit"
```

The command writes a timestamped HTML report, JSON summary, and screenshots
under `reports/visual-audit/`. A `FAIL` is returned as process exit code 2;
browser startup or environment limitations are reported separately as a
blocked condition.

If Playwright is installed but Chromium is missing, install only the browser
component in the project environment:

```powershell
& ".\.venv\Scripts\python.exe" -m playwright install chromium
```
