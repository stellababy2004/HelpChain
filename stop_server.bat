@echo off
echo ========================================
echo    HelpChain Server Stopper
echo ========================================
echo.

echo Stopping HelpChain server...
taskkill /f /im python.exe 2>nul

echo.
echo ✅ Server stopped successfully!
echo ========================================
timeout /t 2 /nobreak >nul
