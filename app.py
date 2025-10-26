import os
import sys

# Change to backend directory to make it the working directory
backend_dir = os.path.join(os.path.dirname(__file__), "backend")
os.chdir(backend_dir)

# Add the backend directory to Python path so we can import modules
sys.path.insert(0, backend_dir)

# Also add the src directory for direct imports
src_dir = os.path.join(backend_dir, "helpchain-backend", "src")
sys.path.insert(0, src_dir)

# Import the Flask app from backend.appy
from appy import app

# This is the Flask application object that Render.com will use
application = app

if __name__ == "__main__":
    app.run()
