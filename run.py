import sys
import os

# Add the backend directory to Python path
backend_dir = os.path.join(
    os.path.dirname(__file__), "backend", "helpchain-backend", "src"
)
sys.path.insert(0, backend_dir)

# Import and run the app
from app import app

if __name__ == "__main__":
    app.run(debug=True)
