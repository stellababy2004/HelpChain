import sys
import os

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

# Import the Flask app
from appy import app

# This is needed for Gunicorn
application = app

if __name__ == "__main__":
    application.run()
