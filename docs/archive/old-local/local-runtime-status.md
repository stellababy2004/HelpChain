# Local Runtime Status

## Canonical interpreter
C:\Users\Stella-PC\AppData\Roaming\uv\python\cpython-3.12-windows-x86_64-none\python.exe

## Canonical startup
& "C:\Users\Stella-PC\AppData\Roaming\uv\python\cpython-3.12-windows-x86_64-none\python.exe" run.py

## Active local DB
C:\dev\HelpChain\instance\hc_local_dev.db

## Fallback local DB
C:\dev\HelpChain\backend\instance\app_clean.db

## Migration command
$env:DATABASE_URL='sqlite:///C:/dev/HelpChain/instance/hc_local_dev.db'
& 'C:\Users\Stella-PC\AppData\Roaming\uv\python\cpython-3.12-windows-x86_64-none\python.exe' .\run_migrations.py

## Verified working routes
- /
- /submit_request
- /admin/login
- /api/pilot-kpi
- /health
- /faq
- /contact

## Verified auth-protected routes
- /admin/
- /admin/requests
- /admin/api/ops-kpis
- /admin/risk-map
- /volunteer/dashboard
