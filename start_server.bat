@echo off
echo ========================================
echo    HelpChain Server Launcher
echo ========================================
echo.

echo [1/4] Stopping any existing Python processes...
taskkill /f /im python.exe 2>nul
timeout /t 2 /nobreak >nul
echo.

echo [2/4] Starting HelpChain server...
echo Server will be available at: http://127.0.0.1:5000
echo.
echo Admin login: http://127.0.0.1:5000/admin_login
echo Username: admin
echo Password: Admin123
echo.
echo Press Ctrl+C to stop the server
echo ========================================

cd /d "%~dp0"
python -c "
import sys
sys.path.insert(0, 'backend')
from appy import app
print('🚀 Starting HelpChain server...')
print('📍 URL: http://127.0.0.1:5000')
print('👤 Admin: admin / Admin123')
print('📧 Volunteer login: http://127.0.0.1:5000/volunteer_login')
print('=' * 50)
app.run(host='127.0.0.1', port=5000, debug=False)
"

echo.
echo Server stopped.
pause
