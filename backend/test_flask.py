#!/usr/bin/env python3
"""
Simple Flask test to check basic functionality
"""
from flask import Flask, jsonify

app = Flask(__name__)


@app.route("/")
def hello():
    return jsonify({"status": "OK", "message": "Simple test Flask app"})


@app.route("/api/test")
def api_test():
    return jsonify({"test": "success", "endpoints": "working"})


if __name__ == "__main__":
    print("🚀 Starting simple test Flask app...")
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
