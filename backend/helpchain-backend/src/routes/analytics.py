import os
import time
import json
from flask import (
    Blueprint,
    render_template,
    request,
    jsonify,
    current_app,
)

analytics_bp = Blueprint(
    "analytics",
    __name__,
    template_folder=os.path.join(os.path.dirname(__file__), "..", "..", "templates"),
)


@analytics_bp.route("/analytics")
def analytics_page():
    return render_template("analytics.html")


@analytics_bp.route("/api/analytics/data")
def analytics_data():
    start = request.args.get("start")
    end = request.args.get("end")
    filters = request.args.get("filters", "")
    sample = {
        "requested": {"start": start, "end": end, "filters": filters},
        "metrics": [
            {"name": "requests", "value": 123},
            {"name": "errors", "value": 5},
            {"name": "avg_response_ms", "value": 240},
        ],
    }
    return jsonify(sample)


def _bookmarks_path():
    path = os.path.join(current_app.instance_path, "analytics_bookmarks.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump([], f)
    return path


@analytics_bp.route("/api/analytics/bookmarks", methods=["GET", "POST", "DELETE"])
def analytics_bookmarks():
    path = _bookmarks_path()
    if request.method == "GET":
        with open(path, "r", encoding="utf-8") as f:
            return jsonify(json.load(f))
    if request.method == "POST":
        payload = request.get_json(force=True)
        with open(path, "r+", encoding="utf-8") as f:
            data = json.load(f)
            data.append(payload)
            f.seek(0)
            f.truncate()
            json.dump(data, f, ensure_ascii=False, indent=2)
        return jsonify(payload), 201
    if request.method == "DELETE":
        name = request.args.get("name")
        with open(path, "r+", encoding="utf-8") as f:
            data = json.load(f)
            data = [b for b in data if b.get("name") != name]
            f.seek(0)
            f.truncate()
            json.dump(data, f, ensure_ascii=False, indent=2)
        return jsonify({"deleted": name}), 200


@analytics_bp.route("/analytics/stream")
def analytics_stream():
    # Non-blocking fallback: връщаме последни n събития като JSON.
    # За реална SSE реализация използвай отделен ASGI endpoint (EventSourceResponse от starlette/fastapi)
    sample_events = [
        {"ts": int(time.time()), "msg": "new_analytics_event"},
    ]
    return jsonify({"sse_enabled": False, "events": sample_events})
