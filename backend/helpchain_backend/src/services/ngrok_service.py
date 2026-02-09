import subprocess
import time

import requests


class NgrokService:
    def __init__(self, port=5005):
        self.port = port
        self.public_url = None

    def start_ngrok(self):
        print("🌐 Стартиране на ngrok тунел...")
        self.ngrok_process = subprocess.Popen(
            ["ngrok", "http", str(self.port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        time.sleep(5)  # Изчакай ngrok да стартира
        self.get_public_url()

    def get_public_url(self):
        try:
            tunnel_info = requests.get(
                "http://127.0.0.1:4040/api/tunnels", timeout=5
            ).json()
            self.public_url = tunnel_info.get("tunnels", [])[0].get("public_url")
            print(f"✅ Публичен адрес: {self.public_url}")
        except Exception as e:
            print("⚠️ Грешка при вземане на ngrok линка:", e)

    def stop_ngrok(self):
        if self.ngrok_process:
            self.ngrok_process.terminate()
            print("🛑 ngrok тунелът е спрян.")
