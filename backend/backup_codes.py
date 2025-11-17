import base64
import hmac
import json
import os
import secrets
import time

try:  # Werkzeug 3.x removed safe_str_cmp; keep optional import
    from werkzeug.security import safe_str_cmp as _safe_str_cmp  # type: ignore
except Exception:
    _safe_str_cmp = None


def _get_pepper() -> bytes:
    pep = os.getenv("HELPCHAIN_2FA_PEPPER")
    if pep:
        return pep.encode("utf-8")
    # Fallback to SECRET_KEY to avoid hard failure; recommend setting dedicated pepper
    return (os.getenv("SECRET_KEY", "dev-secret-pepper")).encode("utf-8")


def _sha256_hex(data: bytes) -> str:
    try:
        import hashlib

        return hashlib.sha256(data).hexdigest()
    except Exception:  # very unlikely, keep minimal fallback
        return ""


def _b64(s: bytes) -> str:
    return base64.urlsafe_b64encode(s).decode("ascii").rstrip("=")


def generate_backup_codes(count: int = 10) -> tuple[list[str], list[dict]]:
    """Generate backup codes and return (plain_codes, records_to_store).

    records_to_store is a list of dicts with fields: salt, hash, used, created_at.
    """
    pepper = _get_pepper()
    plain: list[str] = []
    records: list[dict] = []
    now = int(time.time())

    for _ in range(max(1, int(count))):
        raw = "".join(secrets.choice("0123456789") for _ in range(8))
        display = f"{raw[:4]}-{raw[4:]}"
        salt = secrets.token_bytes(16)
        digest = _sha256_hex(salt + raw.encode("utf-8") + pepper)
        plain.append(display)
        records.append(
            {
                "salt": _b64(salt),
                "hash": digest,
                "used": False,
                "created_at": now,
            }
        )

    return plain, records


def _normalize_code(code: str) -> str:
    code = (code or "").strip()
    return code.replace("-", "").strip()


def verify_and_consume(
    stored_json: str, code: str, *, actor_user_id: int | None = None
) -> tuple[bool, str]:
    """Verify provided code against stored records JSON; mark as used on success.

    Returns (ok, updated_json). When ok is True, updated_json reflects the consumed code.

    If `actor_user_id` is provided, an AuditLog entry with action "backup_code_used"
    is created containing a minimal fingerprint (first 8 chars of the hash) and no
    sensitive plaintext.
    """
    try:
        items = json.loads(stored_json) if stored_json else []
    except Exception:
        items = []

    if not items:
        return False, stored_json or "[]"

    entered = _normalize_code(code)
    if not (entered.isdigit() and len(entered) == 8):
        return False, stored_json

    pepper = _get_pepper()

    for idx, rec in enumerate(items):
        try:
            if rec.get("used"):
                continue
            salt_b64 = rec.get("salt", "")
            try:
                # restore padding for urlsafe_b64
                pad = "=" * (-len(salt_b64) % 4)
                salt = base64.urlsafe_b64decode(salt_b64 + pad)
            except Exception:
                continue
            recomputed = _sha256_hex(salt + entered.encode("utf-8") + pepper)
            # constant-time compare
            target_hash = rec.get("hash", "")
            equal = False
            try:
                equal = hmac.compare_digest(recomputed, target_hash)
            except Exception:
                equal = False
            if not equal and _safe_str_cmp is not None:
                try:
                    equal = _safe_str_cmp(recomputed, target_hash)
                except Exception:
                    equal = False
            if equal:
                # consume
                rec["used"] = True
                items[idx] = rec
                try:
                    updated = json.dumps(items, separators=(",", ":"))
                except Exception:
                    updated = json.dumps(items)
                # Optional audit log
                if actor_user_id is not None:
                    try:
                        # Import lazily to avoid circular imports at module load time
                        from extensions import db  # type: ignore
                        from models import AuditLog  # type: ignore

                        fingerprint = (rec.get("hash", "") or "")[:8]
                        log = AuditLog(
                            actor_user_id=actor_user_id,
                            action="backup_code_used",
                            target_type="admin_user",
                            target_id=str(actor_user_id),
                            outcome="success",
                            metadata_json={"code_hash_prefix": fingerprint},
                        )
                        db.session.add(log)
                        db.session.commit()
                    except Exception:
                        try:
                            db.session.rollback()  # type: ignore
                        except Exception:
                            pass
                return True, updated
        except Exception:
            continue

    # no match
    try:
        updated = json.dumps(items, separators=(",", ":"))
    except Exception:
        updated = json.dumps(items)
    return False, updated


def mask_records_for_display(stored_json: str) -> list[str]:
    """Return a masked list for UI that avoids revealing codes after generation.

    Example: ["••••-••••", "••••-•••• (used)"]
    """
    try:
        items = json.loads(stored_json) if stored_json else []
    except Exception:
        items = []

    masked = []
    for rec in items:
        label = "••••-••••"
        if rec.get("used"):
            label += " (used)"
        masked.append(label)
    return masked
