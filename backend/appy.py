from backend.extensions import db  # bound SQLAlchemy instance
from backend.helpchain_backend.src.app import create_app
import os

# --------------------------------------------------
# Create Flask app
# --------------------------------------------------
app = create_app()


# --------------------------------------------------
# Mail client (stub for dev / tests)
# --------------------------------------------------
class _MailClient:
    def send(self, **kwargs):
        if os.getenv("MAIL_ENABLED", "false") != "true":
            print(f"[MAIL DISABLED] {kwargs}")
            return True

        print(f"[MAIL] Sending email: {kwargs}")
        return True


mail = _MailClient()


# --------------------------------------------------
# 2FA Email helper
# --------------------------------------------------
def send_email_2fa_code(code, ip_address=None, user_agent=None):
    """
    Sends a 2FA verification code via the mail client.
    Compatible with legacy tests.
    """
    subject = "Code de vérification – HelpChain"
    body = f"Votre code de vérification est : {code}\nCe code est valable pendant 10 minutes."

    try:
        result = mail.send(
            subject=subject,
            body=body,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return True if result is None else bool(result)

    except Exception as e:
        # Never break auth flow because of email failure
        print(f"[MAIL ERROR] {e}")
        return False


# --------------------------------------------------
# Optional: helper (useful for scripts/tests)
# --------------------------------------------------
def get_app():
    return app


# --------------------------------------------------
# Public exports
# --------------------------------------------------
__all__ = ["app", "db", "mail", "send_email_2fa_code", "get_app"]