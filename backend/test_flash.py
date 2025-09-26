import os
from dotenv import load_dotenv
load_dotenv()

# Тестов скрипт за симулация на различни flash съобщения
from appy import app

with app.app_context():
    from flask import flash
    
    print("🧪 Тестване на flash съобщенията...")
    
    # Симулираме различни типове съобщения
    flash("✅ Това е success съобщение!", "success")
    flash("❌ Това е error съобщение!", "error") 
    flash("⚠️ Това е warning съобщение!", "warning")
    flash("ℹ️ Това е info съобщение!", "info")
    
    print("Flash съобщенията са зададени. Отворете браузъра за да ги видите.")