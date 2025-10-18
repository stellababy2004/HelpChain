import json
import os
import time

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

try:
    from permissions import require_admin_login
except ImportError:
    from permissions import require_admin_login

analytics_bp = Blueprint("analytics_main", __name__)


@analytics_bp.route("/analytics")
def analytics_page():
    # Redirect to admin analytics if user is admin, otherwise to login
    if session.get("admin_logged_in"):
        return redirect(url_for("admin_analytics"))
    else:
        flash("Аналитиката е достъпна само за администратори.", "info")
        return redirect(url_for("admin_login"))


@analytics_bp.route("/api/analytics/data")
@require_admin_login
def analytics_data():
    try:
        try:
            from analytics_service import analytics_service
        except ImportError:
            from analytics_service import analytics_service

        data = analytics_service.get_dashboard_analytics()
        return jsonify(data)
    except Exception as e:
        print(f"Error getting analytics data: {e}")
        # Fallback to basic stats
        try:
            try:
                from admin_analytics import AnalyticsEngine
            except ImportError:
                from admin_analytics import AnalyticsEngine

            data = AnalyticsEngine.get_dashboard_stats()
            return jsonify(data)
        except Exception as fallback_e:
            print(f"Fallback analytics also failed: {fallback_e}")
            return jsonify({"error": "Analytics not available", "details": str(e)})


def _bookmarks_path():
    path = os.path.join(current_app.instance_path, "analytics_bookmarks.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump([], f)
    return path


@analytics_bp.route("/bookmarks", methods=["GET", "POST", "DELETE"])
def analytics_bookmarks():
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


@analytics_bp.route("/stream")
def analytics_stream():
    # Non-blocking fallback: връщаме последни n събития като JSON.
    # За реална SSE реализация използвай отделен ASGI endpoint
    # (EventSourceResponse от starlette/fastapi)
    sample_events = [
        {"ts": int(time.time()), "msg": "new_analytics_event"},
    ]
    return jsonify({"sse_enabled": False, "events": sample_events})


@analytics_bp.route("/api/analytics/live")
@require_admin_login
def analytics_live():
    """Get live analytics data for real-time updates"""
    try:
        try:
            from analytics_service import analytics_service
        except ImportError:
            from analytics_service import analytics_service

        data = analytics_service.get_dashboard_analytics()

        # Extract live stats from overview
        overview = data.get("overview", {})
        live_data = {
            "requests_today": overview.get("total_page_views", 0),
            "volunteers_active": overview.get("unique_visitors", 0),
            "conversions_today": overview.get("conversions", 0),
            "avg_response_time": overview.get("avg_session_time", 0),
            "timestamp": int(time.time()),
        }
        return jsonify(live_data)
    except Exception as e:
        print(f"Error getting live analytics: {e}")
        return jsonify({"error": "Live analytics not available", "details": str(e)})


@analytics_bp.route("/api/analytics/trends")
@require_admin_login
def analytics_trends():
    """Get trend data for charts"""
    try:
        months = int(request.args.get("months", 6))

        # For now, return mock trend data
        # In a real implementation, this would query historical data
        import datetime

        labels = []
        requests = []
        completed = []
        volunteers = []

        for i in range(months):
            date = datetime.datetime.now() - datetime.timedelta(days=30 * i)
            labels.append(date.strftime("%Y-%m"))
            requests.append(100 + i * 10)  # Mock data
            completed.append(80 + i * 8)
            volunteers.append(50 + i * 5)

        trend_data = {
            "labels": labels[::-1],  # Reverse to show chronological order
            "requests": requests[::-1],
            "completed": completed[::-1],
            "volunteers": volunteers[::-1],
        }
        return jsonify(trend_data)
    except Exception as e:
        print(f"Error getting trend analytics: {e}")
        return jsonify({"error": "Trend analytics not available", "details": str(e)})


@analytics_bp.route("/api/analytics/export")
@require_admin_login
def analytics_export():
    """Export analytics data"""
    try:
        export_format = request.args.get("format", "json")

        try:
            from analytics_service import analytics_service
        except ImportError:
            from analytics_service import analytics_service

        data = analytics_service.get_dashboard_analytics()

        if export_format == "json":
            return jsonify(data)
        elif export_format == "csv":
            # Simple CSV export
            import csv
            from io import StringIO

            output = StringIO()
            writer = csv.writer(output)

            # Write overview data
            writer.writerow(["Metric", "Value"])
            for key, value in data.get("overview", {}).items():
                writer.writerow([key, value])

            csv_data = output.getvalue()
            from flask import Response

            return Response(
                csv_data,
                mimetype="text/csv",
                headers={
                    "Content-Disposition": "attachment; filename=analytics_export.csv"
                },
            )
        else:
            return jsonify({"error": "Unsupported export format"})

    except Exception as e:
        print(f"Error exporting analytics: {e}")
        return jsonify({"error": "Export failed", "details": str(e)})


# Predictive Analytics Routes


@analytics_bp.route("/predictive-analytics")
def predictive_analytics_page():
    """Predictive analytics dashboard page"""
    if not session.get("admin_logged_in"):
        flash("Предиктивната аналитика е достъпна само за администратори.", "info")
        return redirect(url_for("admin_login"))

    return render_template("predictive_analytics.html")


@analytics_bp.route("/api/predictive/regional-demand")
@require_admin_login
def predictive_regional_demand():
    """Get regional demand forecast"""
    try:
        region = request.args.get("region")
        days_ahead = int(request.args.get("days", 7))

        try:
            from predictive_analytics import predictive_analytics
        except ImportError:
            return jsonify(
                {
                    "error": "Predictive analytics not available",
                    "details": "Import failed",
                }
            )

        data = predictive_analytics.get_regional_demand_forecast(
            region=region, days_ahead=days_ahead
        )
        return jsonify(data)

    except Exception as e:
        print(f"Error getting regional demand forecast: {e}")
        return jsonify(
            {"error": "Failed to get regional demand forecast", "details": str(e)}
        )


@analytics_bp.route("/api/predictive/workload")
@require_admin_login
def predictive_workload():
    """Get workload prediction"""
    try:
        hours_ahead = int(request.args.get("hours", 24))

        try:
            from predictive_analytics import predictive_analytics
        except ImportError:
            return jsonify(
                {
                    "error": "Predictive analytics not available",
                    "details": "Import failed",
                }
            )

        data = predictive_analytics.get_workload_prediction(hours_ahead=hours_ahead)
        return jsonify(data)

    except Exception as e:
        print(f"Error getting workload prediction: {e}")
        return jsonify(
            {"error": "Failed to get workload prediction", "details": str(e)}
        )


@analytics_bp.route("/api/predictive/insights")
@require_admin_login
def predictive_insights():
    """Get predictive insights and recommendations"""
    try:
        try:
            from predictive_analytics import predictive_analytics
        except ImportError:
            return jsonify(
                {
                    "error": "Predictive analytics not available",
                    "details": "Import failed",
                }
            )

        data = predictive_analytics.get_predictive_insights()
        return jsonify(data)

    except Exception as e:
        print(f"Error getting predictive insights: {e}")
        return jsonify(
            {"error": "Failed to get predictive insights", "details": str(e)}
        )


@analytics_bp.route("/api/predictive/model-info")
@require_admin_login
def predictive_model_info():
    """Get information about predictive models"""
    try:
        try:
            from predictive_analytics import predictive_analytics
        except ImportError:
            return jsonify(
                {
                    "error": "Predictive analytics not available",
                    "details": "Import failed",
                }
            )

        # Get sample predictions to show model capabilities
        regional_sample = predictive_analytics.get_regional_demand_forecast(
            days_ahead=1
        )
        workload_sample = predictive_analytics.get_workload_prediction(hours_ahead=1)

        model_info = {
            "regional_demand_model": {
                "type": "Random Forest Regression",
                "features": [
                    "day_of_week",
                    "month",
                    "season",
                    "historical_avg",
                    "trend_factor",
                    "volunteer_density",
                    "population_density",
                ],
                "prediction_horizon": "1-30 days",
                "accuracy_metrics": regional_sample.get("model_info", {}).get(
                    "accuracy", "N/A"
                ),
                "last_trained": regional_sample.get("generated_at", "N/A"),
            },
            "workload_prediction_model": {
                "type": "Gradient Boosting Regression",
                "features": [
                    "current_requests",
                    "active_volunteers",
                    "avg_response_time",
                    "day_of_week",
                    "hour_of_day",
                    "season",
                ],
                "prediction_horizon": "1-168 hours",
                "accuracy_metrics": workload_sample.get("model_info", {}).get(
                    "accuracy", "N/A"
                ),
                "last_trained": workload_sample.get("generated_at", "N/A"),
            },
            "data_sources": [
                "HelpRequest table (historical patterns)",
                "Volunteer table (capacity data)",
                "UserActivity table (engagement patterns)",
                "Real-time system metrics",
            ],
            "update_frequency": "Real-time predictions with 1-hour cache",
            "fallback_strategy": "Rule-based heuristics when ML models unavailable",
        }

        return jsonify(model_info)

    except Exception as e:
        print(f"Error getting model info: {e}")
        return jsonify({"error": "Failed to get model information", "details": str(e)})
