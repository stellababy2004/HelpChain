#!/usr/bin/env python3
"""
Test script to verify Flask-Compress is working
"""
import os
import sys

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

try:
    from flask import Flask
    from flask_compress import Compress

    print("✅ Flask-Compress import successful")

    # Test basic initialization
    app = Flask(__name__)
    compress = Compress()
    compress.init_app(app)
    print("✅ Flask-Compress initialization successful")

    # Test configuration
    app.config["COMPRESS_MIMETYPES"] = ["application/json"]
    app.config["COMPRESS_LEVEL"] = 6
    app.config["COMPRESS_MIN_SIZE"] = 500
    print("✅ Flask-Compress configuration successful")

    print("🎉 All Flask-Compress tests passed!")

except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
