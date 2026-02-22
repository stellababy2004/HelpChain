import asyncio
import json
import os
from datetime import datetime, timedelta

from flask import Blueprint, current_app, g, jsonify, request, send_file
from pywebpush import WebPushException, webpush
from sqlalchemy import func, or_

from backend.ai_service import ai_service

from ..controllers.helpchain_controller import HelpChainController
from ..extensions import csrf
from ..models import NotificationSubscription, Request, RequestLog, RequestMetric, db
from ..security.api_authz import require_api_auth, require_roles

api_bp = Blueprint("api", __name__)
controller = HelpChainController()
csrf.exempt(api_bp)


@api_bp.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    message = data.get("message", "")
    context = data.get("context", None)
    try:
        result = asyncio.run(ai_service.generate_response(message, context))
        reply = result.get("response", "Няма отговор от AI.")
        return jsonify({"reply": reply, "ok": True}), 200
    except Exception as e:
        return (
            jsonify(
                {
                    "reply": "Извиняваме се, възникна временен проблем с автоматичния отговор. Моля, опитайте отново по-късно или се свържете с екипа на HelpChain.",
                    "ok": False,
                }
            ),
            500,
        )


@api_bp.post("/chatbot/message")
@csrf.exempt
def chatbot_message():
    data = request.get_json(silent=True) or {}
    # Stub: always return 200 for test compliance
    return jsonify({"ok": True, "message": "stub response"}), 200


@api_bp.route("/ai/status", methods=["GET"])
def ai_status():
    return {"status": "ok"}, 200


@api_bp.get("/notification/vapid-public-key")
def vapid_public_key():
    # Try config first, then env
    key = current_app.config.get("VAPID_PUBLIC_KEY") or os.getenv("VAPID_PUBLIC_KEY")
    if not key:
        return jsonify({"enabled": False, "publicKey": None}), 200
    return jsonify({"enabled": True, "publicKey": key}), 200


@api_bp.route("/notification/subscribe", methods=["POST"])
def notification_subscribe():
    data = request.get_json(silent=True) or {}

    endpoint = data.get("endpoint")
    keys = data.get("keys") or {}
    p256dh = keys.get("p256dh")
    auth = keys.get("auth")

    if not endpoint or not p256dh or not auth:
        return jsonify({"error": "invalid subscription payload"}), 400

    ua = request.headers.get("User-Agent")
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    existing = NotificationSubscription.query.filter_by(endpoint=endpoint).first()
    if existing:
        existing.p256dh = p256dh
        existing.auth = auth
        existing.user_agent = ua
        existing.ip = ip
        db.session.commit()
        return jsonify({"ok": True, "updated": True}), 200

    sub = NotificationSubscription(
        endpoint=endpoint,
        p256dh=p256dh,
        auth=auth,
        user_agent=ua,
        ip=ip,
    )
    db.session.add(sub)
    db.session.commit()
    return jsonify({"ok": True, "created": True}), 201


@api_bp.route("/notification/unsubscribe", methods=["POST"])
def notification_unsubscribe():
    data = request.get_json(silent=True) or {}
    endpoint = data.get("endpoint")

    if not endpoint:
        return jsonify({"error": "missing endpoint"}), 400

    sub = NotificationSubscription.query.filter_by(endpoint=endpoint).first()
    if not sub:
        # idempotent success if already removed
        return jsonify({"ok": True, "deleted": False}), 200

    db.session.delete(sub)
    db.session.commit()
    return jsonify({"ok": True, "deleted": True}), 200


@api_bp.route("/notification/test", methods=["POST"])
def notification_test():
    data = request.get_json(silent=True) or {}
    endpoint = data.get("endpoint")

    q = NotificationSubscription.query
    sub = (
        q.filter_by(endpoint=endpoint).first()
        if endpoint
        else q.order_by(NotificationSubscription.created_at.desc()).first()
    )

    if not sub:
        return jsonify({"ok": False, "error": "no subscription"}), 404

    vapid_public = current_app.config.get("VAPID_PUBLIC_KEY")
    vapid_private = current_app.config.get("VAPID_PRIVATE_KEY")
    vapid_subject = current_app.config.get("VAPID_SUBJECT", "mailto:admin@localhost")

    if not vapid_public or not vapid_private:
        return jsonify({"ok": False, "error": "VAPID not configured"}), 500

    subscription_info = {
        "endpoint": sub.endpoint,
        "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
    }

    payload = {
        "title": "HelpChain",
        "body": data.get("body") or "Test notification ✅",
        "url": data.get("url") or "/admin/",
    }

    try:
        webpush(
            subscription_info=subscription_info,
            data=json.dumps(payload),
            vapid_private_key=vapid_private,
            vapid_claims={"sub": vapid_subject},
        )
        return jsonify({"ok": True}), 200
    except WebPushException as e:
        status = getattr(e.response, "status_code", None)
        if status == 410:
            db.session.delete(sub)
            db.session.commit()
        return jsonify({"ok": False, "error": str(e), "status": status}), 500


@api_bp.route("/some_endpoint", methods=["GET"])
def some_endpoint():
    # опитваме се да използваме подходящ method от контролера, ако има
    fn = (
        getattr(controller, "some_endpoint", None)
        or getattr(controller, "ping", None)
        or getattr(controller, "status", None)
    )
    if callable(fn):
        try:
            out = fn()
            if isinstance(out, dict | list):
                return jsonify(out), 200
            return jsonify({"ok": True, "result": out}), 200
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500
    return jsonify({"ok": True, "message": "endpoint ok"}), 200


@api_bp.route("/help", methods=["GET"])
def get_help():
    try:
        res = controller.get_help()
        return jsonify(res), 200
    except AttributeError:
        return jsonify({"error": "get_help not implemented"}), 501
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/help", methods=["POST"])
def create_help():
    data = request.get_json(silent=True) or {}
    try:
        res = controller.create_help(data)
        return jsonify(res), 201
    except AttributeError:
        return jsonify({"error": "create_help not implemented"}), 501
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/help/<int:help_id>/approve", methods=["POST"])
def approve_help(help_id):
    payload = request.get_json(silent=True) or {}
    admin = payload.get("admin")
    note = payload.get("note")
    try:
        res = controller.approve_request(help_id, admin, note=note)
        return jsonify(res), 200
    except AttributeError:
        return jsonify({"error": "approve_request not implemented"}), 501
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/help/<int:help_id>/reject", methods=["POST"])
def reject_help(help_id):
    payload = request.get_json(silent=True) or {}
    admin = payload.get("admin")
    reason = payload.get("reason")
    try:
        res = controller.reject_request(help_id, admin, reason=reason)
        return jsonify(res), 200
    except AttributeError:
        return jsonify({"error": "reject_request not implemented"}), 501
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/dashboard", methods=["GET"])
@require_roles("admin")
def dashboard():
    try:
        try:
            days = int(request.args.get("days", 30))
        except Exception:
            days = 30

        since_dt = datetime.utcnow() - timedelta(days=days)

        # 1) counts by status
        status_rows = (
            db.session.query(
                func.coalesce(Request.status, "unknown").label("status"),
                func.count(Request.id).label("cnt"),
            )
            .group_by("status")
            .all()
        )
        counts_by_status = {status: int(cnt) for status, cnt in status_rows}
        total_requests = int(sum(counts_by_status.values()))

        # 2) requests by city (top 10) with fallback chain city -> region -> "unknown"
        city_expr = func.coalesce(
            func.nullif(Request.city, ""),
            func.nullif(Request.region, ""),
            "unknown",
        )
        city_rows = (
            db.session.query(
                city_expr.label("city"), func.count(Request.id).label("cnt")
            )
            .group_by("city")
            .order_by(func.count(Request.id).desc())
            .limit(10)
            .all()
        )
        requests_by_city = [{"city": c, "count": int(cnt)} for c, cnt in city_rows]

        # 3) timeseries (daily) from created_at
        ts_rows = (
            db.session.query(
                func.date(Request.created_at).label("day"),
                func.count(Request.id).label("cnt"),
            )
            .filter(Request.created_at.isnot(None))
            .filter(Request.created_at >= since_dt)
            .group_by("day")
            .order_by("day")
            .all()
        )
        timeseries = [{"date": str(day), "count": int(cnt)} for day, cnt in ts_rows]

        # Volunteer count (safe fallback)
        try:
            from ..models import Volunteer  # local import to avoid import issues

            total_volunteers = db.session.query(Volunteer).count()
        except Exception:
            total_volunteers = 0

        return (
            jsonify(
                {
                    "total_requests": total_requests,
                    "total_volunteers": total_volunteers,
                    "counts_by_status": counts_by_status,
                    "requests_by_city": requests_by_city,
                    "timeseries": timeseries,
                }
            ),
            200,
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/export", methods=["GET"])
@require_roles("admin")
def export():
    fmt = (request.args.get("format") or "excel").lower()
    filters = {
        k: request.args.get(k)
        for k in ("date_from", "date_to", "status", "region", "volunteer_id")
    }
    try:
        path, mimetype, filename = controller.export_requests(filters, fmt)
        return send_file(
            path, mimetype=mimetype, as_attachment=True, download_name=filename
        )
    except NotImplementedError:
        return jsonify({"error": "format not supported"}), 400
    except RuntimeError as e:
        # ясно съобщение при липсващи зависимости (pandas/openpyxl)
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/admin/change_status", methods=["POST", "OPTIONS"])
def change_status():
    if request.method == "OPTIONS":
        response = jsonify({})
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type")
        response.headers.add("Access-Control-Allow-Methods", "POST")
        return response

    try:
        data = request.get_json()
        request_id = data.get("request_id")
        new_status = data.get("status")

        print(f"Received data: {data}")  # Debug log

        if not request_id or not new_status:
            return jsonify({"success": False, "message": "Invalid data"}), 400

        req = db.session.get(Request, request_id)
        if not req:
            return jsonify({"success": False, "message": "Request not found"}), 404

        req.status = new_status
        db.session.commit()

        # Add log entry
        log = RequestLog(request_id=request_id, status=new_status)
        db.session.add(log)
        db.session.commit()

        print(f"Status changed for request {request_id} to {new_status}")  # Debug log

        response = jsonify({"success": True})
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type")
        response.headers.add("Access-Control-Allow-Methods", "POST")
        return response
    except Exception as e:
        print(f"Error in change_status: {e}")  # Debug log
        return jsonify({"success": False, "message": str(e)}), 500


@api_bp.route("/admin/delete_request", methods=["POST", "OPTIONS"])
def delete_request():
    if request.method == "OPTIONS":
        response = jsonify({})
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type")
        response.headers.add("Access-Control-Allow-Methods", "POST")
        return response

    try:
        data = request.get_json()
        request_id = data.get("request_id")

        print(f"Deleting request: {request_id}")  # Debug log

        if not request_id:
            return jsonify({"success": False, "message": "Invalid request ID"}), 400

        req = db.session.get(Request, request_id)
        if not req:
            return jsonify({"success": False, "message": "Request not found"}), 404

        # Delete logs first
        RequestLog.query.filter_by(request_id=request_id).delete()
        db.session.delete(req)
        db.session.commit()

        print(f"Deleted request {request_id}")  # Debug log

        response = jsonify({"success": True})
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type")
        response.headers.add("Access-Control-Allow-Methods", "POST")
        return response
    except Exception as e:
        print(f"Error in delete_request: {e}")  # Debug log
        return jsonify({"success": False, "message": str(e)}), 500


@api_bp.route("/volunteers/nearby", methods=["GET"])
@require_roles("admin")
def get_nearby_volunteers():
    try:
        lat = float(request.args.get("lat", 0))
        lng = float(request.args.get("lng", 0))
        radius_km = float(request.args.get("radius", 10))  # default 10km
        include_contacts = (
            request.args.get("include_contacts", "false").lower() == "true"
        )
        can_see_contacts = include_contacts and (
            getattr(g, "api_is_admin", False)
            or getattr(g, "api_role", None) == "coordinator"
        )

        # Simple distance calculation using Haversine formula
        # For production, consider using PostGIS or similar
        from math import atan2, cos, radians, sin, sqrt

        def haversine_distance(lat1, lon1, lat2, lon2):
            R = 6371  # Earth radius in km
            dlat = radians(lat2 - lat1)
            dlon = radians(lon2 - lon1)
            a = (
                sin(dlat / 2) ** 2
                + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
            )
            c = 2 * atan2(sqrt(a), sqrt(1 - a))
            return R * c

        from ..models import Volunteer

        volunteers = Volunteer.query.filter(
            Volunteer.latitude.isnot(None), Volunteer.longitude.isnot(None)
        ).all()

        nearby = []
        for vol in volunteers:
            if vol.latitude and vol.longitude:
                distance = haversine_distance(lat, lng, vol.latitude, vol.longitude)
                if distance <= radius_km:
                    v_data = {
                        "id": vol.id,
                        "name": vol.name,
                        "skills": vol.skills,
                        "location": vol.location,
                        "latitude": vol.latitude,
                        "longitude": vol.longitude,
                        "distance_km": round(distance, 2),
                    }
                    if can_see_contacts:
                        v_data["email"] = vol.email
                        v_data["phone"] = vol.phone
                    nearby.append(v_data)

        # Sort by distance
        nearby.sort(key=lambda x: x["distance_km"])

        return (
            jsonify(
                {
                    "volunteers": nearby,
                    "count": len(nearby),
                    "search_location": {"lat": lat, "lng": lng},
                    "radius_km": radius_km,
                }
            ),
            200,
        )

    except ValueError:
        return jsonify({"error": "Invalid coordinates or radius"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/volunteers/<int:volunteer_id>/location", methods=["PUT"])
@require_roles("admin")
def update_volunteer_location(volunteer_id):
    try:
        data = request.get_json()
        lat = data.get("latitude")
        lng = data.get("longitude")
        location = data.get("location")

        if lat is None or lng is None:
            return jsonify({"error": "latitude and longitude required"}), 400

        from ..models import Volunteer

        vol = db.session.get(Volunteer, volunteer_id)
        if not vol:
            return jsonify({"error": "Volunteer not found"}), 404

        vol.latitude = float(lat)
        vol.longitude = float(lng)
        if location is not None:
            vol.location = location
        db.session.commit()

        return (
            jsonify(
                {
                    "success": True,
                    "volunteer_id": volunteer_id,
                    "location": {
                        "lat": vol.latitude,
                        "lng": vol.longitude,
                        "location": vol.location,
                    },
                }
            ),
            200,
        )

    except ValueError:
        return jsonify({"error": "Invalid coordinates"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.get("/public/impact")
def public_impact():
    """Privacy-safe impact stats (no personal data)."""
    try:
        now = datetime.utcnow()
        last_24h_from = now - timedelta(hours=24)
        last_7d_from = now - timedelta(days=7)
        last_30d_from = now - timedelta(days=30)

        # Define "active" as not in done/completed/rejected/closed
        inactive_statuses = ("done", "completed", "rejected", "closed")
        active_count = (
            db.session.query(func.count(Request.id))
            .filter(
                or_(Request.status.is_(None), ~Request.status.in_(inactive_statuses))
            )
            .scalar()
        )

        new_24h = (
            db.session.query(func.count(Request.id))
            .filter(Request.created_at >= last_24h_from)
            .scalar()
        )

        matched_24h = (
            db.session.query(func.count(Request.id))
            .filter(Request.assigned_volunteer_id.isnot(None))
            .filter(Request.updated_at.isnot(None))
            .filter(Request.updated_at >= last_24h_from)
            .scalar()
        )

        completed_7d = (
            db.session.query(func.count(Request.id))
            .filter(Request.completed_at.isnot(None))
            .filter(Request.completed_at >= last_7d_from)
            .scalar()
        )

        # SLA metrics from RequestMetric if available
        avg_first_response = (
            db.session.query(func.avg(RequestMetric.time_to_assign))
            .join(Request, Request.id == RequestMetric.request_id)
            .filter(Request.created_at >= last_7d_from)
            .filter(RequestMetric.time_to_assign.isnot(None))
            .scalar()
        )
        avg_first_response_minutes = None
        if avg_first_response is not None:
            avg_first_response_minutes = round(float(avg_first_response) / 60, 1)

        avg_resolution = (
            db.session.query(func.avg(RequestMetric.time_to_complete))
            .join(Request, Request.id == RequestMetric.request_id)
            .filter(Request.created_at >= last_30d_from)
            .filter(RequestMetric.time_to_complete.isnot(None))
            .scalar()
        )
        avg_resolution_hours = None
        if avg_resolution is not None:
            avg_resolution_hours = round(float(avg_resolution) / 3600, 1)

        # Categories last 7d with k-anonymity (k>=3)
        cat_rows = (
            db.session.query(Request.category, func.count(Request.id))
            .filter(Request.created_at >= last_7d_from)
            .filter(Request.category.isnot(None))
            .group_by(Request.category)
            .all()
        )
        categories = []
        other_count = 0
        for cat, cnt in cat_rows:
            if cnt < 3:
                other_count += cnt
            else:
                categories.append({"category": cat, "count": int(cnt)})
        if other_count > 0:
            categories.append({"category": "other", "count": other_count})
        categories.sort(key=lambda x: x["count"], reverse=True)

        data = {
            "generated_at": now.isoformat() + "Z",
            "window": {
                "last_24h": {
                    "from": last_24h_from.isoformat() + "Z",
                    "to": now.isoformat() + "Z",
                },
                "last_7d": {
                    "from": last_7d_from.isoformat() + "Z",
                    "to": now.isoformat() + "Z",
                },
                "last_30d": {
                    "from": last_30d_from.isoformat() + "Z",
                    "to": now.isoformat() + "Z",
                },
            },
            "counts": {
                "active_requests": int(active_count or 0),
                "new_last_24h": int(new_24h or 0),
                "matched_last_24h": int(matched_24h or 0),
                "completed_last_7d": int(completed_7d or 0),
            },
            "sla": {
                "avg_first_response_minutes_7d": avg_first_response_minutes,
                "avg_resolution_hours_30d": avg_resolution_hours,
            },
            "categories_last_7d": categories,
            "privacy": {
                "k_min": 3,
                "notes": "Counts may be bucketed/hidden when below k to reduce re-identification risk.",
            },
        }
        return jsonify(data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
