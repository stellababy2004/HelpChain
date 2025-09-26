cdimport subprocess
import time
import requests
import webbrowser
import os

# Стартирай Flask приложението в нова конзола
print("🚀 Стартиране на Flask сървъра...")
flask = subprocess.Popen(
    ["cmd", "/k", "cd backend && venv\\Scripts\\activate && python app.py"],
    creationflags=subprocess.CREATE_NEW_CONSOLE,
)

# Изчакай Flask да стартира
time.sleep(5)

# Стартирай ngrok (ако е инсталиран и желаеш тунел)
print("🌐 Стартиране на ngrok тунел...")
ngrok = subprocess.Popen(
    ["cmd", "/k", "ngrok http 5000"], creationflags=subprocess.CREATE_NEW_CONSOLE
)

# Изчакай ngrok да стартира
time.sleep(5)

# Вземи публичния линк от локалния web интерфейс на ngrok
public_url = None
try:
    tunnel = requests.get("http://127.0.0.1:4040/api/tunnels", timeout=5).json()
    public_url = tunnel.get("tunnels", [])[0].get("public_url")
    print(f"✅ Публичен адрес: {public_url}")
except Exception as e:
    print("⚠️ Грешка при вземане на ngrok линка:", e)

# Автоматично отвори линка в браузър (ако е намерен)
if public_url:
    try:
        webbrowser.open(public_url)
    except Exception:
        pass

# Създай QR код за телефона
img = qrcode.make(public_url)
qr_path = "helpchain_qr.png"
img.save(qr_path)
print(f"📱 QR кодът е запазен като {qr_path}")
os.startfile(qr_path)
