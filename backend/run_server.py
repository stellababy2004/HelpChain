#!/usr/bin/env python3
import sys
import os
import subprocess

# Path to virtual environment Python
venv_python = r"C:\Users\Stella Barbarella\OneDrive\Documents\chatGPT\Projet BG\HelpChain\backend\.venv\Scripts\python.exe"

if __name__ == "__main__":
    print("Starting HelpChain server with virtual environment...")

    # Re-run this script with the virtual environment Python
    if sys.executable != venv_python:
        print(f"Switching to virtual environment: {venv_python}")
        try:
            subprocess.run([venv_python, __file__])
        except Exception as e:
            print(f"Error running with virtual environment: {e}")
            sys.exit(1)
        sys.exit(0)

    # Now we're running with the virtual environment
    print("Running with virtual environment Python")
    sys.path.insert(0, ".")

    try:
        from appy import app

        print("Flask app imported successfully")
        app.run(
            host="127.0.0.1", port=5000, debug=False, use_reloader=False, threaded=True
        )
    except Exception as e:
        print(f"Error starting server: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
