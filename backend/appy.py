import os

from backend.extensions import db  # re-export the bound SQLAlchemy instance
from backend.helpchain_backend.src.app import create_app

app = create_app()


class _MailClient:
    def send(self, **kwargs):
        return True


mail = _MailClient()


def send_email_2fa_code(code, ip_address=None, user_agent=None):
    """
    Legacy helper used by older tests.
    Sends a 2FA code email via backend.appy.mail.send.
    """
    subject = "Votre code de vérification"
    body = f"Votre code de vérification est : {code}"
    result = mail.send(
        subject=subject, body=body, ip_address=ip_address, user_agent=user_agent
    )
    return True if result is None else bool(result)


# За Render health: ако искаш бърз sanity
@app.get("/health")
def health():
    return {"ok": True, "git": os.getenv("GIT_SHA", "unknown")}, 200


__all__ = ["app", "db", "mail", "send_email_2fa_code"]
