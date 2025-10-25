#!/usr/bin/env python
"""
Simple test server for load testing
"""

from flask import Flask, jsonify

app = Flask(__name__)


@app.route("/")
def home():
    return jsonify({"message": "Hello from test server", "status": "ok"})


@app.route("/api/test")
def api_test():
    return jsonify({"data": "test response", "success": True})


@app.route("/api/slow")
def slow_endpoint():
    import time

    time.sleep(0.1)  # 100ms delay
    return jsonify({"data": "slow response", "delay": "100ms"})


if __name__ == "__main__":
    print("Starting simple test server on http://127.0.0.1:5001")
    app.run(host="127.0.0.1", port=5001, debug=False, threaded=True)
