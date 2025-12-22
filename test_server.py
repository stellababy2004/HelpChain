#!/usr/bin/env python3
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(HERE, "backend")

# Ensure backend is importable
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

def main():
    print("Starting server...")
    print(f"Project root: {HERE}")
    print(f"Backend dir  : {BACKEND_DIR}")

    try:
        # Import after sys.path is set
        from appy import app  # backend/appy.py must define `app`
    except Exception as e:
        print(f"Error importing app from backend/appy.py: {e}")
        traceback.print_exc()
        sys.exit(1)

    try:
        # Run Flask without reloader to avoid double-start issues
        app.run(
            host="127.0.0.1",
            port=5000,
            debug=False,
            use_reloader=False,
            threaded=False,
        )
    except Exception as e:
        print(f"Error starting server: {e}")
        traceback.print_exc()
        sys.exit(2)

if __name__ == "__main__":
    main()
