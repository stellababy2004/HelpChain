@echo off
cd /d C:\dev\HelpChain.bg
taskkill /f /im python.exe 2>nul
timeout /t 1 /nobreak >nul
set HC_DB_PATH=C:\dev\HelpChain.bg\instance\hc_local_dev.db
set SQLALCHEMY_DATABASE_URI=sqlite:///C:/dev/HelpChain.bg/instance/hc_local_dev.db
set PORT=5000
start "HelpChain Server" cmd /k "cd /d C:\dev\HelpChain.bg && set HC_DB_PATH=C:\dev\HelpChain.bg\instance\hc_local_dev.db && set SQLALCHEMY_DATABASE_URI=sqlite:///C:/dev/HelpChain.bg/instance/hc_local_dev.db && set PORT=5000 && C:\dev\HelpChain.bg\.venv\Scripts\python.exe run.py"
timeout /t 3 /nobreak >nul
echo Server started on http://127.0.0.1:5000
