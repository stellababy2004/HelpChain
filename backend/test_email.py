import os
from flask import Flask
from flask_mail import Mail, Message

app = Flask(__name__)
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USE_SSL"] = False
app.config["MAIL_USERNAME"] = "stelabarbarella@gmail.com"
app.config["MAIL_PASSWORD"] = "rixujwrltldciqnd"
app.config["MAIL_DEFAULT_SENDER"] = "contact@helpchain.live"

mail = Mail(app)

with app.app_context():
    try:
        msg = Message("Test Email", recipients=["contact@helpchain.live"])
        msg.body = "This is a test email from HelpChain"
        mail.send(msg)
        print("Email sent successfully!")
    except Exception as e:
        print(f"Failed to send email: {e}")
