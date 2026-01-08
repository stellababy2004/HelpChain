@echo off
REM Run schema drift guard before CRUD smoke tests
python scripts\schema_drift_guard.py
if %ERRORLEVEL% NEQ 0 exit /b 1
python scripts\db_crud_smoke.py
