import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from src.app import create_app

app = create_app()
print("App created successfully")
