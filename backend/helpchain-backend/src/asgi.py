from asgiref.wsgi import WsgiToAsgi
from .app import app as flask_app

asgi_app = WsgiToAsgi(flask_app)

# Добави mock за mail.send за тестване (симулира изпращане без реални SMTP заявки)
from unittest.mock import patch

# Mock mail.send за всички изпращания на имейли
mock_mail_send = patch(
    "flask_mail.Mail.send",
    side_effect=lambda msg: print(
        f"Mocked email sent: {msg.subject} to {msg.recipients}"
    )
    or None,
).start()

# За да спреш mock-а в production, добави:
# mock_mail_send.stop()  # Премахни за реални имейли
