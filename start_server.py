#!/usr/bin/env python3
"""
HelpChain Server Launcher
Simple script to start the HelpChain Flask application
"""

import os
import platform
import signal
import subprocess
import sys
import time


def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    print("\n\n🛑 Stopping HelpChain server...")
    sys.exit(0)


def main():
    # Register signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)

    print("=" * 50)
    print("🚀 HelpChain Server Launcher")
    print("=" * 50)

    # Change to script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    # Stop any existing Python processes
    print("📋 [1/3] Stopping existing Python processes...")
    if platform.system() == "Windows":
        subprocess.run(["taskkill", "/f", "/im", "python.exe"], capture_output=True)
    else:
        subprocess.run(["pkill", "-f", "python"], capture_output=True)
    time.sleep(1)

    # Check if we can import the app
    print("🔍 [2/3] Checking application...")
    try:
        sys.path.insert(0, "backend")
        from appy import app

        print("✅ Application loaded successfully!")
        print(f"📊 Routes registered: {len(app.url_map._rules)}")
    except Exception as e:
        print(f"❌ Error loading application: {e}")
        sys.exit(1)

    # Start the server
    print("🌟 [3/3] Starting server...")
    print("=" * 50)
    print("📍 Server URL: http://127.0.0.1:5000")
    print("👨‍💼 Admin login: http://127.0.0.1:5000/admin_login")
    print("   Username: admin")
    print("   Password: Admin123")
    print("👥 Volunteer login: http://127.0.0.1:5000/volunteer_login")
    print("🤖 AI Chatbot: http://127.0.0.1:5000/api/chatbot/message")
    print("=" * 50)
    print("💡 Press Ctrl+C to stop the server")
    print()

    try:
        app.run(host="127.0.0.1", port=5000, debug=False)
    except KeyboardInterrupt:
        print("\n\n🛑 Server stopped by user")
    except Exception as e:
        print(f"\n❌ Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
