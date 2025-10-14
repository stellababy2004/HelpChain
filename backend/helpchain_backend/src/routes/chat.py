import os

from flask import Blueprint, current_app, jsonify, request
from flask_login import login_required
from werkzeug.utils import secure_filename

from ...analytics_service import analytics_service
from ...models import ChatMessage, ChatRoom

chat_bp = Blueprint("chat", __name__)


@chat_bp.route("/chat/history/<room>")
@login_required
def get_chat_history(room):
    chat_room = ChatRoom.query.filter_by(name=room).first()
    if not chat_room:
        return jsonify([])
    messages = (
        ChatMessage.query.filter_by(room_id=chat_room.id)
        .order_by(ChatMessage.timestamp)
        .all()
    )
    history = [
        {
            "username": msg.user.username,
            "message": msg.content,
            "file_path": msg.file_path,
            "timestamp": str(msg.timestamp),
        }
        for msg in messages
    ]
    analytics_service.track_event(
        "chat_history", "engagement", "view_history", {"room": room}
    )
    return jsonify(history)


@chat_bp.route("/chat/upload", methods=["POST"])
@login_required
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "Няма файл"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Няма избран файл"}), 400
    filename = secure_filename(file.filename)
    file_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
    file.save(file_path)
    analytics_service.track_event(
        "file_upload", "engagement", "upload_file", {"filename": filename}
    )
    return jsonify({"file_path": file_path})


# Регистрирайте в app.py: app.register_blueprint(chat_bp, url_prefix='/api/chat')
