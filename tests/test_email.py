import os
from flask import Flask
from flask_mail import Mail, Message

app = Flask(__name__)
app.config["MAIL_SERVER"] = "smtp.zoho.eu"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USE_SSL"] = False
app.config["MAIL_USERNAME"] = "contact@helpchain.live"
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD", "REPLACE_ME")
app.config["MAIL_DEFAULT_SENDER"] = "contact@helpchain.live"

mail = Mail(app)

with app.app_context():
    try:
        msg = Message(
            "🎉 HelpChain - Zoho Professional Email Setup Complete!",
            recipients=["contact@helpchain.live"],
        )
        msg.body = """Поздравления! 🎊

Zoho Mail е успешно настроен като професионално решение за HelpChain!

✅ SMTP конфигурация: smtp.zoho.eu:587 (TLS)
✅ 2FA App Password: Активиран и работещ
✅ Production Ready: Системата е готова за deployment

Технически детайли:
- Доставчик: Zoho Mail (Европа)
- Порт: 587 с TLS шифриране
- Акаунт: contact@helpchain.live
- Статус: Професионално решение активно

Сега всички имейл нотификации ще се изпращат през Zoho!

Дата: 8 октомври 2025
Система: HelpChain.bg"""
        mail.send(msg)
        print("✅ Email sent successfully via Zoho Professional SMTP!")
        print("🎉 HelpChain is now configured for production email delivery!")
        print("📧 All notifications will be sent through Zoho Mail")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        print("💡 Check your Zoho app password or try regenerating it")
