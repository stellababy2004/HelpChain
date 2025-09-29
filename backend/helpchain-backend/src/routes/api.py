from flask import Blueprint, request, jsonify, send_file
from ..controllers.helpchain_controller import HelpChainController

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
            if isinstance(out, (dict, list)):
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
