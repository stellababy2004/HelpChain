import sys
import os
from waitress import serve

backend_dir = os.path.join(os.path.dirname(__file__), "backend")
sys.path.insert(0, backend_dir)

from appy import app

if __name__ == "__main__":
    print("🚀 HelpChain server starting with Waitress...")
    print("📍 http://127.0.0.1:5000")
    print("👤 Admin: admin / Admin123")
    print("Press Ctrl+C to stop")
    serve(app, host="127.0.0.1", port=5000)
