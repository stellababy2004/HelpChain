import os

import pyotp
from cryptography.fernet import Fernet

from models import User


def _get_fernet() -> Fernet:
    key = os.getenv("FERNET_KEY")
    if not key:
        raise RuntimeError(
            "FERNET_KEY must be set in environment (export or GH secret)"
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def generate_2fa_secret_for_user(user: User) -> tuple[str, str]:
    """
    Генерира TOTP secret, шифрова го и го записва в user.twofa_secret_encrypted.
    Caller трябва да запише/комитне промяната в DB.
    Връща (plain_secret, provisioning_uri) за показване/QR.
    """
    secret = pyotp.random_base32()
    uri = pyotp.totp.TOTP(secret).provisioning_uri(
        name=user.email, issuer_name="HelpChain"
    )
    fernet = _get_fernet()
    user.twofa_secret_encrypted = fernet.encrypt(secret.encode()).decode()
    return secret, uri


def verify_2fa_token(user: User, token: str, valid_window: int = 1) -> bool:
    """
    Верифицира подадения TOTP token срещу шифрования secret.
    valid_window позволява +/- интервал за тайм синхрон.
    """
    if not user.twofa_secret_encrypted:
        return False
    try:
        fernet = _get_fernet()
        secret = fernet.decrypt(user.twofa_secret_encrypted.encode()).decode()
    except Exception:
        return False
    totp = pyotp.TOTP(secret)
    return totp.verify(token, valid_window=valid_window)


def disable_2fa(user: User) -> None:
    """Премахва 2FA secret (caller трябва да запише промените)."""
    user.twofa_secret_encrypted = None
