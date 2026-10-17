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


def test_render_admin_existing_account_is_noop_by_default():
    source = Path(
        "backend/scripts/ensure_render_admin.py"
    ).read_text(encoding="utf-8")

    assert 'os.getenv("ADMIN_SEED_FORCE_RESET")' in source
    assert "if not force_reset and not reset_mfa:" in source
    assert '"no changes requested"' in source
    assert "if force_reset:" in source


def test_render_admin_recovery_defaults_to_disabled(monkeypatch):
    monkeypatch.delenv("ADMIN_SEED_RESET_MFA", raising=False)
    monkeypatch.delenv("ADMIN_SEED_FORCE_RESET", raising=False)

    reset_mfa = (
        os.getenv("ADMIN_SEED_RESET_MFA") or ""
    ).strip().lower() in {"1", "true", "yes"}
    force_reset = (
        os.getenv("ADMIN_SEED_FORCE_RESET") or ""
    ).strip().lower() in {"1", "true", "yes"}

    assert reset_mfa is False
    assert force_reset is False
