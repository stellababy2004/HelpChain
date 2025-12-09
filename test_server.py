#!/usr/bin/env python
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from appy import app

if __name__ == "__main__":
    print("Starting server...")
    try:
        app.run(
            host="127.0.0.1", port=5000, debug=False, use_reloader=False, threaded=False
        )
    except Exception as e:
        print(f"Error starting server: {e}")
        import traceback

        traceback.print_exc()
