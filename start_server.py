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

    # Stop any existing Python processes (optional)
    # Skippable via HELPCHAIN_SKIP_KILL=1 to avoid killing unrelated Python tasks
    skip_kill = os.environ.get("HELPCHAIN_SKIP_KILL") in ("1", "true", "True")
    if skip_kill:
        print("⏭️  [1/3] Skipping mass-kill of Python processes (HELPCHAIN_SKIP_KILL=1)")
    else:
        print("📋 [1/3] Stopping existing Python processes...")
        try:
            if platform.system() == "Windows":
                subprocess.run(["taskkill", "/f", "/im", "python.exe"], capture_output=True)
            else:
                subprocess.run(["pkill", "-f", "python"], capture_output=True)
            time.sleep(1)
        except Exception:
            # Non-fatal; continue starting server
            pass

    # Check if we can import the canonical app factory (avoid legacy entrypoints like `appy`).
    print("🔍 [2/3] Checking application import path...")
    try:
        __import__("backend.helpchain_backend.src.app")
        print("✅ Canonical app factory is importable: backend.helpchain_backend.src.app:create_app")
    except Exception as e:
        print(f"❌ Error importing canonical app factory: {e}")
        sys.exit(1)

    # Start the server (canonical entrypoint)
    PORT = os.environ.get("PORT", "5005")
    host = os.environ.get("HOST", "127.0.0.1")

    print("🌟 [3/3] Starting server...")
    print("=" * 50)
    print(f"📍 Server URL: http://{host}:{PORT}")
    print(f"👨‍💼 Admin:      http://{host}:{PORT}/admin/ops/login")
    print(f"👥 Volunteer:   http://{host}:{PORT}/volunteer_login")
    print(f"🧾 Legal:       http://{host}:{PORT}/legal")
    print(f"🤖 AI Chatbot:  http://{host}:{PORT}/api/chatbot/message")
    print("=" * 50)
    print("💡 Press Ctrl+C to stop the server")
    print()

    # Keep it deterministic: avoid cookie/csrf split by changing secrets between runs.
    os.environ.setdefault("SECRET_KEY", "dev-secret-keep-constant-123")

    cmd = [
        sys.executable, "-m", "flask",
        "--app", "backend.helpchain_backend.src.app:create_app",
        "run",
        "--host", host,
        "--port", str(PORT),
        "--no-reload",
    ]
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\n\n🛑 Server stopped by user")
    except Exception as e:
        print(f"\n❌ Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
