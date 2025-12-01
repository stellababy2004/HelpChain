import os

try:
    import pyotp  # type: ignore
    from cryptography.fernet import Fernet  # type: ignore
    _AUTH_2FA_AVAILABLE = True
except Exception:  # pragma: no cover - optional deps may be missing in test env
    pyotp = None  # type: ignore
    Fernet = None  # type: ignore
    _AUTH_2FA_AVAILABLE = False

from backend.models import User


def _get_fernet() -> "Fernet":
    if not _AUTH_2FA_AVAILABLE:
        raise RuntimeError("Optional 2FA dependencies not installed (pyotp/cryptography)")
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
    if not _AUTH_2FA_AVAILABLE:
        raise RuntimeError("2FA support is not available in this environment")
    secret = pyotp.random_base32()  # type: ignore
    uri = pyotp.totp.TOTP(secret).provisioning_uri(
        name=user.email, issuer_name="HelpChain"  # type: ignore
    )
    fernet = _get_fernet()
    user.twofa_secret_encrypted = fernet.encrypt(secret.encode()).decode()
    return secret, uri


def verify_2fa_token(user: User, token: str, valid_window: int = 1) -> bool:
    """
    Верифицира подадения TOTP token срещу шифрования secret.
    valid_window позволява +/- интервал за тайм синхрон.
    """
    if not _AUTH_2FA_AVAILABLE:
        return False
    if not user.twofa_secret_encrypted:
        return False
    try:
        fernet = _get_fernet()
        secret = fernet.decrypt(user.twofa_secret_encrypted.encode()).decode()
    except Exception:
        return False
    totp = pyotp.TOTP(secret)  # type: ignore
    return totp.verify(token, valid_window=valid_window)


def disable_2fa(user: User) -> None:
    """Премахва 2FA secret (caller трябва да запише промените)."""
    user.twofa_secret_encrypted = None
