# 🚀 Стартиране на HelpChain с Waitress (производствен режим)
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "   🔐 Стартиране на стабилен HelpChain сървър" -ForegroundColor Green
Write-Host "   🌐 Адрес: http://127.0.0.1:8000" -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Cyan

# Отиваме в backend директорията на проекта
cd "C:\Users\Stella Barbarella\OneDrive\Documents\chatGPT\Projet BG\HelpChain\backend"

# Проверка дали waitress е инсталиран
if (-not (pip show waitress)) {
    Write-Host "📦 Инсталирам waitress..." -ForegroundColor Yellow
    pip install waitress
}

# Стартиране на сървъра с waitress
Write-Host "🟢 Стартиране на Waitress сървъра..." -ForegroundColor Green
waitress-serve --listen=127.0.0.1:8000 appy:app

# При спиране:
Write-Host "🔴 Сървърът е спрян." -ForegroundColor Red
