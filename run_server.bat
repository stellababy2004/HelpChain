@echo off
echo ========================================
echo    HelpChain Server - Direct Start
echo ========================================
echo.

cd /d "%~dp0"
python -c "import sys; sys.path.insert(0, 'backend'); from appy import app; print('🚀 HelpChain server started!'); print('📍 http://127.0.0.1:5000'); print('👤 Admin: admin / test-password'); print('Press Ctrl+C to stop'); app.run(host='127.0.0.1', port=5000, debug=False)"

pause

