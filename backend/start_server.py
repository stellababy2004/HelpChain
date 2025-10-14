#!/usr/bin/env python
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(__file__))

from appy import app

if __name__ == "__main__":
    print("🚀 Starting HelpChain Server...")
    print("📍 Access at: http://localhost:5000")
    print("🤖 Chatbot at: http://localhost:5000/chatbot")
    print("Press Ctrl+C to stop")

    app.run(debug=True, host="127.0.0.1", port=5000, use_reloader=False)
