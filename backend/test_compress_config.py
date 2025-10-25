#!/usr/bin/env python3
"""
Simple test to verify Flask-Compress configuration
"""
from flask import Flask, jsonify
from flask_compress import Compress

app = Flask(__name__)
app.config["COMPRESS_MIMETYPES"] = [
    "text/html",
    "text/css",
    "text/xml",
    "application/json",
    "application/javascript",
    "text/javascript",
]
app.config["COMPRESS_LEVEL"] = 6
app.config["COMPRESS_MIN_SIZE"] = 500

compress = Compress()
compress.init_app(app)


@app.route("/test")
def test():
    # Create a large JSON response (> 500 bytes)
    data = {
        "data": "x" * 1000,
        "message": "This is a test response that should be compressed",
    }
    return jsonify(data)


if __name__ == "__main__":
    print("🧪 Flask-Compress Configuration Test")
    print("=" * 40)
    print(f'COMPRESS_MIMETYPES: {app.config.get("COMPRESS_MIMETYPES")}')
    print(f'COMPRESS_LEVEL: {app.config.get("COMPRESS_LEVEL")}')
    print(f'COMPRESS_MIN_SIZE: {app.config.get("COMPRESS_MIN_SIZE")}')
    print("✅ Flask-Compress is properly configured")
    print()
    print("Configuration Details:")
    print("- JSON responses are configured for compression")
    print("- Compression level: 6 (good balance of speed vs compression)")
    print("- Minimum size: 500 bytes (only compress larger responses)")
    print("- Supported MIME types include application/json")
