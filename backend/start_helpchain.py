# ...existing code...
import os
import subprocess
import time
import webbrowser
from pathlib import Path

import requests

try:
    import qrcode
except Exception:
    qrcode = None

PROJECT_DIR = Path(__file__).resolve().parent

print("🚀 Стартиране на Flask сървъра...")
venv_python = PROJECT_DIR / "venv" / "Scripts" / "python.exe"
if venv_python.exists():
    flask_cmd_str = f'"{venv_python}" "{PROJECT_DIR / "app.py"}"'
else:
    flask_cmd_str = f'python "{PROJECT_DIR / "app.py"}"'

flask = subprocess.Popen(
    ["cmd", "/k", flask_cmd_str],
    creationflags=subprocess.CREATE_NEW_CONSOLE,
)

time.sleep(5)

print("🌐 Стартиране на ngrok тунел...")
ngrok = subprocess.Popen(
    ["cmd", "/k", "ngrok http 5000"], creationflags=subprocess.CREATE_NEW_CONSOLE
)

time.sleep(5)

public_url = None
try:
    r = requests.get("http://127.0.0.1:4040/api/tunnels", timeout=5)
    tunnels = r.json().get("tunnels", [])
    if tunnels:
        public_url = tunnels[0].get("public_url")
        print(f"✅ Публичен адрес: {public_url}")
except Exception as e:
    print("⚠️ Грешка при вземане на ngrok линка:", e)

if public_url:
    try:
        webbrowser.open(public_url)
    except Exception:
        pass

if public_url and qrcode:
    try:
        img = qrcode.make(public_url)
        qr_path = PROJECT_DIR / "helpchain_qr.png"
        img.save(qr_path)
        print(f"📱 QR кодът е запазен като {qr_path}")
        try:
            os.startfile(qr_path)
        except Exception:
            pass
    except Exception as e:
        print("⚠️ Неуспешно генериране на QR:", e)
elif public_url and qrcode is None:
    print('⚠️ Модулът qrcode не е инсталиран. Инсталирай с: pip install "qrcode[pil]"')
