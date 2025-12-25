from flask import Flask, request
from http.server import BaseHTTPRequestHandler
from vercel_python import VercelRequest, VercelResponse
import json

app = Flask(__name__)


@app.route("/api/csp-report", methods=["POST"])
def csp_report():
    try:
        data = request.json()
        print("CSP report:", data)
    except Exception as e:
        print("CSP report error:", str(e))
    response.status_code = 204
    return ""


def handler(request, response):
    try:
        data = request.json()
        print("CSP report:", data)
    except Exception as e:
        print("CSP report error:", str(e))
    response.status_code = 204
    return ""
