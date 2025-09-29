from flask import Blueprint, request, jsonify
from src.controllers.helpchain_controller import HelpChainController

api_bp = Blueprint("api", __name__)
controller = HelpChainController()


@api_bp.route("/help", methods=["GET"])
def get_help():
    response = controller.get_help()
    return jsonify(response)


@api_bp.route("/help", methods=["POST"])
def create_help():
    data = request.json
    response = controller.create_help(data)
    return jsonify(response), 201


@api_bp.route("/help/<int:help_id>", methods=["GET"])
def get_help_by_id(help_id):
    response = controller.get_help_by_id(help_id)
    return jsonify(response)


@api_bp.route("/help/<int:help_id>", methods=["PUT"])
def update_help(help_id):
    data = request.json
    response = controller.update_help(help_id, data)
    return jsonify(response)


@api_bp.route("/help/<int:help_id>", methods=["DELETE"])
def delete_help(help_id):
    response = controller.delete_help(help_id)
    return jsonify(response), 204


@api_bp.route("/some_endpoint", methods=["GET"])
def some_endpoint():
    return jsonify({"ok": True, "message": "endpoint ok"}), 200
