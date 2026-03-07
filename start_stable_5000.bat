@echo off
cd /d C:\dev\HelpChain.bg
set HC_DB_PATH=C:\dev\HelpChain.bg\instance\hc_local_dev.db
set SQLALCHEMY_DATABASE_URI=sqlite:///C:/dev/HelpChain.bg/instance/hc_local_dev.db
set PORT=5000
echo Starting HelpChain on http://127.0.0.1:5000
echo Keep this window open.
C:\dev\HelpChain.bg\.venv\Scripts\python.exe run.py
