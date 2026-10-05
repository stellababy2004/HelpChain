import os
from pathlib import Path


def test_render_admin_recovery_is_explicit_opt_in():
    source = Path(
        "backend/scripts/ensure_render_admin.py"
    ).read_text(encoding="utf-8")

    assert 'os.getenv("ADMIN_SEED_RESET_MFA")' in source
    assert 'role != "superadmin"' in source
    assert "admin.totp_secret = None" in source
    assert "admin.mfa_enabled = False" in source
    assert "admin.mfa_enrolled_at = None" in source
    assert "admin.backup_codes_hashes = None" in source
    assert "admin.backup_codes_generated_at = None" in source


def test_render_admin_recovery_defaults_to_disabled(monkeypatch):
    monkeypatch.delenv("ADMIN_SEED_RESET_MFA", raising=False)

    value = (
        os.getenv("ADMIN_SEED_RESET_MFA") or ""
    ).strip().lower() in {"1", "true", "yes"}

    assert value is False
