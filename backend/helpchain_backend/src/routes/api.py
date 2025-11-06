from flask import Blueprint, jsonify, request, send_file

from ..controllers.helpchain_controller import HelpChainController
from ..models import Request, RequestLog, db

api_bp = Blueprint("api", __name__)
controller = HelpChainController()


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
def dashboard():
    filters = {
        "date_from": request.args.get("date_from"),
        "date_to": request.args.get("date_to"),
        "status": request.args.get("status"),
        "region": request.args.get("region"),
        "volunteer_id": request.args.get("volunteer_id"),
    }
    try:
        data = controller.get_dashboard_stats(filters)
        return jsonify(data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/export", methods=["GET"])
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

        req = Request.query.get(request_id)
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

        req = Request.query.get(request_id)
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
def get_nearby_volunteers():
    try:
        lat = float(request.args.get("lat", 0))
        lng = float(request.args.get("lng", 0))
        radius_km = float(request.args.get("radius", 10))  # default 10km

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
                    nearby.append(
                        {
                            "id": vol.id,
                            "name": vol.name,
                            "email": vol.email,
                            "phone": vol.phone,
                            "skills": vol.skills,
                            "location": vol.location,
                            "latitude": vol.latitude,
                            "longitude": vol.longitude,
                            "distance_km": round(distance, 2),
                        }
                    )

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
def update_volunteer_location(volunteer_id):
    try:
        data = request.get_json()
        lat = data.get("latitude")
        lng = data.get("longitude")
        location = data.get("location")

        if lat is None or lng is None:
            return jsonify({"error": "latitude and longitude required"}), 400

        from ..models import Volunteer

        vol = Volunteer.query.get(volunteer_id)
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
