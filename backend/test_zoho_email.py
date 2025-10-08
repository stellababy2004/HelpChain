import os
from flask import Flask
from flask_mail import Mail, Message

app = Flask(__name__)

# Зареди от .env
app.config["MAIL_SERVER"] = os.getenv("MAIL_SERVER", "smtp.zoho.eu")
app.config["MAIL_PORT"] = int(os.getenv("MAIL_PORT", 465))
app.config["MAIL_USE_SSL"] = os.getenv("MAIL_USE_SSL", "True") == "True"
app.config["MAIL_USE_TLS"] = os.getenv("MAIL_USE_TLS", "False") == "True"
app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME", "contact@helpchain.live")
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD")
app.config["MAIL_DEFAULT_SENDER"] = os.getenv(
    "MAIL_DEFAULT_SENDER", "contact@helpchain.live"
)

mail = Mail(app)

with app.app_context():
    try:
        msg = Message(
            subject="Тест: Нов доброволец в HelpChain",
            recipients=["contact@helpchain.live"],
            sender=app.config["MAIL_USERNAME"],  # Използвай username като sender
            body="""Тестово съобщение за нов доброволец:

Име: Test User
Имейл: test@example.com
Телефон: 123456789
Локация: Sofia

Това е тест за проверка на имейл функционалността.
""",
        )
        mail.send(msg)
        print("Имейлът е изпратен успешно!")
    except Exception as e:
        print(f"Грешка при изпращане на имейл: {e}")
