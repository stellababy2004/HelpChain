import os
import time
import json
from flask import (
    Blueprint,
    render_template,
    request,
    jsonify,
    current_app,
    session,
    redirect,
    url_for,
    flash,
)

analytics_bp = Blueprint(
    "analytics",
    __name__,
    template_folder=os.path.join(os.path.dirname(__file__), "..", "..", "templates"),
)


@analytics_bp.route("/analytics")
def analytics_page():
    # Redirect to admin analytics if user is admin, otherwise to login
    if session.get("admin_logged_in"):
        return redirect(url_for("admin_analytics"))
    else:
        flash("Аналитиката е достъпна само за администратори.", "info")
        return redirect(url_for("admin_login"))


@analytics_bp.route("/api/analytics/data")
def analytics_data():
    # Require admin login for analytics data
    if not session.get("admin_logged_in"):
        return jsonify({"error": "Unauthorized"}), 403

    from ..models import Request, Volunteer
    from collections import Counter

    # Get requests data
    requests = Request.query.all()

    # Status distribution
    status_counts = Counter(r.status for r in requests)
    status_labels = list(status_counts.keys())
    status_data = list(status_counts.values())

    # Category distribution
    category_counts = Counter(r.category for r in requests if r.category)
    category_labels = list(category_counts.keys())
    category_data = list(category_counts.values())

    # Urgency distribution
    urgency_counts = Counter(r.urgency for r in requests if r.urgency)
    urgency_labels = list(urgency_counts.keys())
    urgency_data = list(urgency_counts.values())

    # Location distribution
    location_counts = Counter(r.location for r in requests if r.location)
    location_labels = list(location_counts.keys())
    location_data = list(location_counts.values())

    # Volunteer data
    volunteers = Volunteer.query.all()

    # Volunteer location distribution
    volunteer_location_counts = Counter(v.location for v in volunteers if v.location)
    volunteer_location_labels = list(volunteer_location_counts.keys())
    volunteer_location_data = list(volunteer_location_counts.values())

    # Volunteer skills distribution (simplified - count volunteers with skills)
    volunteers_with_skills = [v for v in volunteers if v.skills]
    skills_counts = {}
    for v in volunteers_with_skills:
        skills = v.skills.split(",") if v.skills else []
        for skill in skills:
            skill = skill.strip()
            if skill:
                skills_counts[skill] = skills_counts.get(skill, 0) + 1

    volunteer_skills_labels = list(skills_counts.keys())[:10]  # Top 10 skills
    volunteer_skills_data = [skills_counts[label] for label in volunteer_skills_labels]

    return jsonify(
        {
            "status_labels": status_labels,
            "status_data": status_data,
            "category_labels": category_labels,
            "category_data": category_data,
            "urgency_labels": urgency_labels,
            "urgency_data": urgency_data,
            "location_labels": location_labels,
            "location_data": location_data,
            "volunteer_location_labels": volunteer_location_labels,
            "volunteer_location_data": volunteer_location_data,
            "volunteer_skills_labels": volunteer_skills_labels,
            "volunteer_skills_data": volunteer_skills_data,
        }
    )


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
    # Require admin login for stream
    if not session.get("admin_logged_in"):
        return jsonify({"error": "Unauthorized"}), 403

    # Non-blocking fallback: връщаме последни n събития като JSON.
    # За реална SSE реализация използвай отделен ASGI endpoint (EventSourceResponse от starlette/fastapi)
    sample_events = [
        {"ts": int(time.time()), "msg": "new_analytics_event"},
    ]
    return jsonify({"sse_enabled": False, "events": sample_events})
