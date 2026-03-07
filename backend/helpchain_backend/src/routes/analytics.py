import json
import os
import time

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    request,
    session,
    url_for,
)
from flask_babel import gettext as _

from ..extensions import csrf

analytics_bp = Blueprint(
    "analytics",
    __name__,
    template_folder=os.path.join(os.path.dirname(__file__), "..", "..", "templates"),
)
csrf.exempt(analytics_bp)


@analytics_bp.route("/analytics")
def analytics_page():
    # Redirect to admin analytics if user is admin, otherwise to login
    if session.get("admin_logged_in"):
        return redirect(url_for("admin_analytics"))
    else:
        flash(_("Analytics is available only to administrators."), "info")
        return redirect(url_for("admin_login"))


@analytics_bp.route("/api/analytics/data")
def analytics_data():
    # Require admin login for analytics data
    if not session.get("admin_logged_in"):
        return jsonify({"error": "Unauthorized"}), 403

    try:
        from ....analytics_service import analytics_service

        # Get dashboard analytics from analytics service
        dashboard_data = analytics_service.get_dashboard_analytics(days=30)

        return jsonify(dashboard_data)

    except Exception as e:
        current_app.logger.error(f"Error getting analytics data: {e}")
        return jsonify({"error": "Failed to load analytics data"}), 500


def _bookmarks_path():
    path = os.path.join(current_app.instance_path, "analytics_bookmarks.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump([], f)
    return path


@analytics_bp.route("/api/analytics/bookmarks", methods=["GET", "POST", "DELETE"])
def analytics_bookmarks():
    # Require admin login for bookmarks
    if not session.get("admin_logged_in"):
        return jsonify({"error": "Unauthorized"}), 403

    path = _bookmarks_path()
    if request.method == "GET":
        with open(path, encoding="utf-8") as f:
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
    # Require admin login for stream
    if not session.get("admin_logged_in"):
        return jsonify({"error": "Unauthorized"}), 403

    # Non-blocking fallback: връщаме последни n събития като JSON.
    # За реална SSE реализация използвай отделен ASGI endpoint (EventSourceResponse от starlette/fastapi)
    sample_events = [
        {"ts": int(time.time()), "msg": "new_analytics_event"},
    ]
    return jsonify({"sse_enabled": False, "events": sample_events})
