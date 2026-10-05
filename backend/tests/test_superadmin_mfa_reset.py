from pathlib import Path
from backend.extensions import db
from backend.models import AdminUser


def test_superadmin_mfa_reset_route_exists():
    source = Path(
        "backend/helpchain_backend/src/routes/admin.py"
    ).read_text(encoding="utf-8")

    assert '@admin_bp.post("/platform/users/<int:member_id>/reset-mfa")' in source
    assert 'def superadmin_user_reset_mfa(member_id):' in source
    assert 'member.totp_secret = None' in source
    assert 'member.mfa_enabled = False' in source
    assert 'member.mfa_enrolled_at = None' in source
    assert 'member.backup_codes_hashes = None' in source
    assert 'member.backup_codes_generated_at = None' in source
    assert 'action="SUPERADMIN_MFA_RESET"' in source


def test_superadmin_mfa_reset_blocks_self_reset():
    source = Path(
        "backend/helpchain_backend/src/routes/admin.py"
    ).read_text(encoding="utf-8")

    assert "if member.id == actor.id:" in source
    assert "abort(403)" in source

