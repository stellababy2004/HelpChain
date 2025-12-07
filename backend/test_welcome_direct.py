# ...existing code...
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Директен тест на welcome имейл функцията
"""

import os
import smtplib
import ssl
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Зареждаме environment променливи
from dotenv import load_dotenv

load_dotenv()


def _build_email(volunteer_name, volunteer_email, volunteer_location, template_path, sender):
    if not os.path.exists(template_path):
        raise FileNotFoundError(template_path)
    with open(template_path, encoding="utf-8") as f:
        html_body = f.read()
    html_body = html_body.replace("{{volunteer_name}}", volunteer_name)
    html_body = html_body.replace("{{volunteer_email}}", volunteer_email)
    html_body = html_body.replace("{{volunteer_location}}", volunteer_location)

    subject = f"🎉 Добре дошли в HelpChain.bg, {volunteer_name}!"
    msg = MIMEMultipart("alternative")
    msg["From"] = sender
    msg["To"] = volunteer_email
    msg["Subject"] = Header(subject, "utf-8").encode()
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    return msg, html_body, subject


def send_welcome_email(
    volunteer_name,
    volunteer_email,
    volunteer_location,
    template_path,
    smtp_class=smtplib.SMTP_SSL,
):
    smtp_server = os.getenv("MAIL_SERVER", "smtp.example")
    smtp_port = int(os.getenv("MAIL_PORT", 465))
    smtp_username = os.getenv("MAIL_USERNAME", "")
    smtp_password = os.getenv("MAIL_PASSWORD", "")
    smtp_sender = os.getenv("MAIL_DEFAULT_SENDER", "noreply@example.com")

    msg, _, _ = _build_email(volunteer_name, volunteer_email, volunteer_location, template_path, smtp_sender)

    context = ssl.create_default_context()
    with smtp_class(smtp_server, smtp_port, context=context) as server:
        if smtp_username and smtp_password:
            server.login(smtp_username, smtp_password)
        server.send_message(msg)


# Тест, който не прави реални мрежови повиквания
def test_welcome_email_monkeypatched(tmp_path, monkeypatch):
    # Подготвяме временен template файл
    email_dir = tmp_path / "email_templates"
    email_dir.mkdir()
    template_file = email_dir / "volunteer_welcome.html"
    template_content = "<html><body>Welcome {{volunteer_name}} &lt;{{volunteer_email}}&gt; from {{volunteer_location}}</body></html>"
    template_file.write_text(template_content, encoding="utf-8")

    # Настройваме env променливи
    monkeypatch.setenv("MAIL_SERVER", "smtp.test")
    monkeypatch.setenv("MAIL_PORT", "465")
    monkeypatch.setenv("MAIL_USERNAME", "user")
    monkeypatch.setenv("MAIL_PASSWORD", "pass")
    monkeypatch.setenv("MAIL_DEFAULT_SENDER", "noreply@test")

    # Dummy SMTP, който записва последното съобщение
    class DummySMTP:
        last_instance = None

        def __init__(self, *args, **kwargs):
            DummySMTP.last_instance = self

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def login(self, user, pwd):
            self.logged = (user, pwd)

        def send_message(self, msg):
            self.sent_msg = msg

    monkeypatch.setattr(smtplib, "SMTP_SSL", DummySMTP)

    # Call the function (uses dummy SMTP)
    send_welcome_email(
        "Тест Потребител",
        "test@example.com",
        "София",
        str(template_file),
        smtp_class=smtplib.SMTP_SSL,
    )

    # Asserts — проверяваме че DummySMTP е бил използван и имейлът съдържа правилния текст
    assert DummySMTP.last_instance is not None
    sent = getattr(DummySMTP.last_instance, "sent_msg", None)
    assert sent is not None
    body = sent.get_payload()[0].get_payload(decode=True).decode("utf-8")
    assert "Тест Потребител" in body
    assert "test@example.com" in body
    assert "София" in body


# ...existing code...
