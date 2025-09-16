import os, ssl, smtplib
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv(".env")

MAIL_SERVER = os.getenv("MAIL_SERVER") or os.getenv("SMTP_HOST")
MAIL_PORT = int(os.getenv("MAIL_PORT") or os.getenv("SMTP_PORT") or 587)
MAIL_USER = os.getenv("MAIL_USERNAME") or os.getenv("SMTP_USER")
MAIL_PASS = os.getenv("MAIL_PASSWORD") or os.getenv("SMTP_PASS")
USE_SSL = os.getenv("MAIL_USE_SSL", "False").lower() in ("1","true","yes")

msg = EmailMessage()
msg["Subject"] = "HelpChain тест"
msg["From"] = f"HelpChain <{MAIL_USER}>"
msg["To"] = "your-email@example.com"  # замени с адрес, който можеш да четеш
msg.set_content("Текстова версия")
msg.add_alternative("<p>HTML тест от HelpChain</p>", subtype="html")

print("Config:", MAIL_SERVER, MAIL_PORT, "SSL=", USE_SSL, "USER=", MAIL_USER)

try:
    if USE_SSL or MAIL_PORT==465:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(MAIL_SERVER, MAIL_PORT, context=context, timeout=20) as smtp:
            if MAIL_USER and MAIL_PASS:
                smtp.login(MAIL_USER, MAIL_PASS)
            smtp.send_message(msg)
    else:
        context = ssl.create_default_context()
        with smtplib.SMTP(MAIL_SERVER, MAIL_PORT, timeout=20) as smtp:
            smtp.starttls(context=context)
            if MAIL_USER and MAIL_PASS:
                smtp.login(MAIL_USER, MAIL_PASS)
            smtp.send_message(msg)
    print("Email изпратен успешно.")
except Exception as e:
    print("Email send error:", repr(e))