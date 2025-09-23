cdimport subprocess
import time
import requests
import webbrowser
import os
import qrcode

# Стартирай Flask приложението
print("🚀 Стартиране на Flask сървъра...")
flask = subprocess.Popen(
    ["cmd", "/k", "cd backend && venv\\Scripts\\activate && python app.py"],
    creationflags=subprocess.CREATE_NEW_CONSOLE,
)

# Изчакай Flask да се стартира
time.sleep(5)

# Стартирай Ngrok
print("🌐 Стартиране на ngrok тунел...")
ngrok = subprocess.Popen(
    ["cmd", "/k", "ngrok http 5000"], creationflags=subprocess.CREATE_NEW_CONSOLE
)

# Изчакай още малко за ngrok
time.sleep(5)

# Вземи публичния линк от локалния web интерфейс
try:
    tunnel = requests.get("http://127.0.0.1:4040/api/tunnels").json()
    public_url = tunnel["tunnels"][0]["public_url"]
    print(f"✅ Публичен адрес: {public_url}")
except Exception as e:
    print("⚠️ Грешка при вземане на ngrok линка:", e)
    public_url = None

# Отвори линка в браузър
if public_url:
    webbrowser.open(public_url)

    # Създай QR код за телефона
    img = qrcode.make(public_url)
    qr_path = "helpchain_qr.png"
    img.save(qr_path)
    print(f"📱 QR кодът е запазен като {qr_path}")
    os.startfile(qr_path)
