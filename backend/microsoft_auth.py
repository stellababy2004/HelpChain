"""Microsoft OIDC (passwordless) integration blueprint.

Implements:
 - Authorization Code + PKCE flow
 - Token exchange (code -> id_token/access_token) via `requests`
 - id_token validation: signature (JWKS), required claims (iss,aud,exp,nonce,sub)
 - User provisioning / binding (`ms_oid`) and password disabling

Security notes:
 - Requires environment/config: MICROSOFT_TENANT_ID, MICROSOFT_CLIENT_ID, optional MICROSOFT_CLIENT_SECRET
 - For public/native apps omit client secret and mark app as public in Azure registration.
 - JWKS cached in-memory with TTL to reduce network calls.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
from datetime import datetime, timezone
from urllib.parse import urlencode

import requests
from flask import Blueprint, current_app, flash, redirect, request, session, url_for

try:
    from authlib.jose import JsonWebKey, JsonWebToken
except Exception:
    JsonWebToken = None  # type: ignore
    JsonWebKey = None  # type: ignore

try:
    from .models import User, db  # type: ignore
except Exception:
    from models import User, db  # type: ignore

bp = Blueprint("msauth", __name__, url_prefix="/auth/microsoft")

# Configuration keys expected (tenant-specific)
# MICROSOFT_TENANT_ID, MICROSOFT_CLIENT_ID, MICROSOFT_CLIENT_SECRET (optional if confidential)
# For public/native style with PKCE we may omit secret.
AUTHORITY_TEMPLATE = "https://login.microsoftonline.com/{tenant}"
V2_SUFFIX = "/v2.0"
TOKEN_ENDPOINT = "/oauth2/v2.0/token"
AUTH_ENDPOINT = "/oauth2/v2.0/authorize"
OPENID_CONFIG_SUFFIX = "/.well-known/openid-configuration"
SCOPES = ["openid", "profile", "email"]

# Simple in-memory nonce store (can be moved to DB/Redis later)
_nonce_cache: dict[str, float] = {}
NONCE_TTL = 300  # seconds
_jwks_cache: dict[str, object] = {}
_jwks_cached_at: float | None = None
JWKS_TTL = 3600  # 1 hour


def _get_cfg(key: str, default: str | None = None) -> str | None:
    return current_app.config.get(key) or os.getenv(key) or default


def _authority() -> str:
    tenant = _get_cfg("MICROSOFT_TENANT_ID", "common")
    return AUTHORITY_TEMPLATE.format(tenant=tenant)


def _auth_base() -> str:
    return _authority().rstrip("/") + AUTH_ENDPOINT


def _token_url() -> str:
    return _authority().rstrip("/") + TOKEN_ENDPOINT


def _openid_config_url() -> str:
    return _authority().rstrip("/") + OPENID_CONFIG_SUFFIX


def _build_auth_url(nonce: str, state: str, code_challenge: str) -> str:
    client_id = _get_cfg("MICROSOFT_CLIENT_ID")
    redirect_uri = url_for("msauth.callback", _external=True)
    query = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "response_mode": "query",
        "scope": " ".join(SCOPES),
        "state": state,
        "nonce": nonce,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return _auth_base() + "?" + urlencode(query)


def _generate_code_verifier() -> str:
    return secrets.token_urlsafe(64)


def _code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def _store_nonce(nonce: str):
    _nonce_cache[nonce] = time.time()


def _validate_and_consume_nonce(nonce: str) -> bool:
    ts = _nonce_cache.get(nonce)
    if ts is None:
        return False
    if time.time() - ts > NONCE_TTL:
        _nonce_cache.pop(nonce, None)
        return False
    _nonce_cache.pop(nonce, None)
    return True


def _fetch_jwks(force: bool = False) -> dict[str, object]:
    global _jwks_cache, _jwks_cached_at
    now = time.time()
    if (
        not force
        and _jwks_cached_at
        and (now - _jwks_cached_at) < JWKS_TTL
        and _jwks_cache
    ):
        return _jwks_cache
    try:
        cfg_resp = requests.get(_openid_config_url(), timeout=5)
        cfg_resp.raise_for_status()
        jwks_uri = cfg_resp.json().get("jwks_uri")
        if not jwks_uri:
            raise ValueError("jwks_uri missing in openid configuration")
        jwks_resp = requests.get(jwks_uri, timeout=5)
        jwks_resp.raise_for_status()
        data = jwks_resp.json()
        _jwks_cache = data
        _jwks_cached_at = now
        return data
    except Exception as e:
        flash(f"Грешка при зареждане на JWKS: {e}", "error")
        return {}


def _validate_id_token(id_token: str, nonce: str) -> dict[str, object] | None:
    if not JsonWebToken or not JsonWebKey:
        flash("ID token validation library не е достъпна.", "error")
        return None
    jwks = _fetch_jwks()
    if not jwks:
        return None
    try:
        jwt_obj = JsonWebToken(["RS256", "RS512"])
        claims = jwt_obj.decode(id_token, JsonWebKey.import_key_set(jwks))
        claims.validate()  # exp, nbf, iat
        # Required claims
        client_id = _get_cfg("MICROSOFT_CLIENT_ID")
        issuer_expected = _authority().rstrip("/") + V2_SUFFIX
        if claims.get("iss") != issuer_expected:
            flash("Невалиден issuer в id_token.", "error")
            return None
        if claims.get("aud") != client_id:
            flash("Невалиден audience в id_token.", "error")
            return None
        if claims.get("nonce") != nonce:
            flash("Nonce несъответствие.", "error")
            return None
        if not claims.get("sub"):
            flash("Липсва sub claim.", "error")
            return None
        return claims
    except Exception as e:
        flash(f"Грешка при валидация на id_token: {e}", "error")
        return None


def _exchange_code_for_tokens(code: str) -> dict[str, object] | None:
    client_id = _get_cfg("MICROSOFT_CLIENT_ID")
    client_secret = _get_cfg("MICROSOFT_CLIENT_SECRET")  # may be None for public apps
    verifier = session.get("pkce_verifier")
    redirect_uri = url_for("msauth.callback", _external=True)
    data = {
        "client_id": client_id,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "code_verifier": verifier,
    }
    if client_secret:
        data["client_secret"] = client_secret
    try:
        resp = requests.post(_token_url(), data=data, timeout=6)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        flash(f"Неуспешен обмен на код: {e}", "error")
        return None


@bp.route("/start", methods=["POST"])
def start():
    """Step 1: collect required email before Microsoft redirect.

    Expects form field `email`. Stores in session then initiates OIDC auth.
    """
    email = (request.form.get("email") or "").strip()
    if not email or "@" not in email:
        flash("Моля въведете валиден имейл.", "error")
        return redirect(url_for("index"))
    session["pending_email"] = email
    # Prepare PKCE + nonce + state
    code_verifier = _generate_code_verifier()
    session["pkce_verifier"] = code_verifier
    code_challenge = _code_challenge(code_verifier)
    nonce = secrets.token_urlsafe(16)
    state = secrets.token_urlsafe(16)
    session["oidc_state"] = state
    _store_nonce(nonce)
    auth_url = _build_auth_url(nonce, state, code_challenge)
    return redirect(auth_url)


@bp.route("/login", methods=["GET"])
def login():
    """Optional direct login (skip email capture if already bound)."""
    # If user already logged in or has pending email, reuse.
    if "pending_email" not in session:
        flash("Първо въведете имейл за регистрация.", "error")
        return redirect(url_for("index"))
    # Reuse start logic via a synthetic POST? Simpler: call start pieces.
    code_verifier = _generate_code_verifier()
    session["pkce_verifier"] = code_verifier
    code_challenge = _code_challenge(code_verifier)
    nonce = secrets.token_urlsafe(16)
    state = secrets.token_urlsafe(16)
    session["oidc_state"] = state
    _store_nonce(nonce)
    auth_url = _build_auth_url(nonce, state, code_challenge)
    return redirect(auth_url)


@bp.route("/callback", methods=["GET"])
def callback():
    """OIDC redirect handler: code->tokens, id_token validation, provisioning."""
    code = request.args.get("code")
    state = request.args.get("state")
    expected_state = session.get("oidc_state")
    if not code or not state or state != expected_state:
        flash("Неуспешен вход (state mismatch).", "error")
        return redirect(url_for("index"))

    nonce = None
    # We stored nonce only in ephemeral cache; keep a copy in session for validation.
    # For improved reliability, put nonce in session during start/login.
    nonce = session.pop("oidc_nonce", None)

    tokens = _exchange_code_for_tokens(code)
    if not tokens:
        return redirect(url_for("index"))
    id_token = tokens.get("id_token")
    if not id_token:
        flash("Липсва id_token в отговора.", "error")
        return redirect(url_for("index"))

    # If nonce is not in session (older start), attempt to rely on original param (best-effort).
    if not nonce:
        nonce = request.args.get("nonce")
    if nonce and not _validate_and_consume_nonce(nonce):
        flash("Nonce validation failed.", "error")
        return redirect(url_for("index"))

    claims = _validate_id_token(id_token, nonce or "")
    if not claims:
        return redirect(url_for("index"))

    ms_oid = str(claims.get("sub"))[:120]
    email = (
        session.pop("pending_email", None)
        or claims.get("email")
        or claims.get("preferred_username")
    )
    if not email:
        flash("Неуспешен вход – липсва имейл.", "error")
        return redirect(url_for("index"))
    # Find existing user by ms_oid or email
    user = None
    if ms_oid:
        user = User.query.filter_by(ms_oid=ms_oid).first()
    if user is None:
        user = User.query.filter_by(email=email).first()
    if user is None:
        # Provision new user; generate synthetic username from email local-part.
        local_part = email.split("@", 1)[0]
        base_username = local_part[:100] or f"user{secrets.randbelow(10**6)}"
        candidate = base_username
        i = 0
        while User.query.filter_by(username=candidate).first() is not None:
            i += 1
            candidate = f"{base_username}{i}"[:120]
        user = User(username=candidate, email=email, role=None)
        # Set a random strong password (will be disabled immediately)
        rand_pwd = secrets.token_urlsafe(24)
        user.set_password(rand_pwd)
        db.session.add(user)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            flash("Грешка при създаване на акаунт.", "error")
            return redirect(url_for("index"))
    # Bind Microsoft OID + disable password
    user.bind_microsoft_oid(ms_oid)

    session["user_logged_in"] = True
    session["user_id"] = user.id
    session["user_role"] = getattr(user.role, "value", "user")
    flash("Успешен вход (passwordless Microsoft).", "success")
    return redirect(url_for("index"))


# Future enhancements:
# - Refresh token handling (offline_access scope)
# - Revoke sessions via Microsoft sign-out
# - Persist JWKS to disk or Redis for multi-process
# - Additional claim checks (tid, ver)
# - Structured audit logging for binds & logins

__all__ = ["bp"]
