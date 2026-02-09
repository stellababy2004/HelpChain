import base64
import io
import json
import secrets

import pyotp
import qrcode
from werkzeug.security import check_password_hash, generate_password_hash


def get_totp_uri(username: str, secret: str, issuer: str = "HelpChain") -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name=issuer)


def verify_totp(token: str, secret: str) -> bool:
    totp = pyotp.TOTP(secret)
    return totp.verify(token, valid_window=1)


def qr_base64(uri: str) -> str:
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


# Backwards-friendly aliases
def generate_totp_secret() -> str:
    return pyotp.random_base32()


def build_totp_uri(secret: str, username: str, issuer: str = "HelpChain") -> str:
    return get_totp_uri(username=username, secret=secret, issuer=issuer)


def verify_totp_code(secret: str, code: str) -> bool:
    try:
        code = (code or "").strip().replace(" ", "")
    except Exception:
        pass
    return verify_totp(code, secret)


def qr_png_base64(data: str) -> str:
    return qr_base64(data)


def generate_backup_codes(n: int = 10) -> list[str]:
    return [secrets.token_hex(4).upper() for _ in range(n)]


def hash_backup_codes(codes: list[str]) -> list[str]:
    return [generate_password_hash(c) for c in codes]


def backup_codes_to_text(hashes: list[str]) -> str:
    return json.dumps(hashes)


def backup_codes_from_text(txt: str | None) -> list[str]:
    if not txt:
        return []
    try:
        return json.loads(txt)
    except Exception:
        return []


def consume_backup_code(user, code: str) -> bool:
    code = (code or "").strip().upper().replace(" ", "")
    hashes = backup_codes_from_text(getattr(user, "backup_codes_hashes", None))
    if not hashes:
        return False
    for i, h in enumerate(hashes):
        if check_password_hash(h, code):
            hashes.pop(i)
            user.backup_codes_hashes = backup_codes_to_text(hashes)
            return True
    return False
