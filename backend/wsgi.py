import sys
import os

# Add the backend directory to Python path so we can import models
backend_dir = os.path.dirname(__file__)
sys.path.insert(0, backend_dir)

# Also add parent directory in case we need it
parent_dir = os.path.dirname(backend_dir)
sys.path.insert(0, parent_dir)

print(f"Python path: {sys.path[:3]}...")  # Debug print
print(f"Current directory: {os.getcwd()}")

# Import the Flask app
from appy import app

# This is needed for Gunicorn
application = app

if __name__ == "__main__":
    application.run()
