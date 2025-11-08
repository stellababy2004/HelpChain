#!/usr/bin/env python3
"""
Celery Worker Startup Script for HelpChain
"""

import os
import sys
from pathlib import Path

# Add backend directory to Python path
backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))

# Set environment variables for Celery
os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:6379/0")
os.environ.setdefault("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

if __name__ == "__main__":
    # Import and run Celery after path setup
    from backend.celery_app import celery

    celery.start()
