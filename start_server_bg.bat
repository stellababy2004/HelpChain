@echo off
echo ========================================
echo    HelpChain Server Launcher (Background)
echo ========================================
echo.

echo [1/3] Stopping any existing Python processes...
taskkill /f /im python.exe 2>nul
timeout /t 1 /nobreak >nul

echo [2/3] Starting HelpChain server in background...
powershell -Command "Start-Job -ScriptBlock { Set-Location 'c:\Users\Stella Barbarella\OneDrive\Documents\chatGPT\Projet BG\HelpChain'; python start_server.py } | Out-Null"

echo [3/3] Waiting for server to start...
timeout /t 5 /nobreak >nul

echo.
echo ✅ Server should be running now!
echo 🌐 Open browser: http://127.0.0.1:5000
echo 👨‍💼 Admin panel: http://127.0.0.1:5000/admin_login
echo 👥 Volunteer login: http://127.0.0.1:5000/volunteer_login
echo.
echo 💡 To stop server: Run 'stop_server.bat'
echo ========================================
