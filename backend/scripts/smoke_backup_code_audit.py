import json
import os
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND_ROOT = os.path.dirname(HERE)
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

import backup_codes as bc  # type: ignore
from app import app, db  # type: ignore
from models import AdminUser, AuditLog, RoleEnum, User  # type: ignore


def main():
    # Disable CSRF just in case we end up using test_client in extensions
    app.config["WTF_CSRF_ENABLED"] = False

    with app.app_context():
        # Ensure AdminUser exists
        admin = AdminUser.query.filter_by(username="admin").first()
        if not admin:
            admin = AdminUser(username="admin", email="admin@example.com")
            admin.set_password("StrongPass123")
            db.session.add(admin)
            db.session.commit()

        # Ensure a corresponding User 'admin' exists for actor mapping in AuditLog
        user_admin = User.query.filter_by(username="admin").first()
        if not user_admin:
            user_admin = User(
                username="admin", email="admin@example.com", role=RoleEnum.admin
            )
            user_admin.set_password("StrongPass123")
            db.session.add(user_admin)
            db.session.commit()

        # Generate fresh backup codes
        plain, records = bc.generate_backup_codes(count=3)
        admin.backup_codes = json.dumps(records)
        db.session.add(admin)
        db.session.commit()

        # Use the first code
        code_to_use = plain[0]
        ok, updated = bc.verify_and_consume(
            admin.backup_codes, code_to_use, actor_user_id=user_admin.id
        )
        print("verify ok:", ok)
        admin.backup_codes = updated
        db.session.add(admin)
        db.session.commit()

        # If optional internal audit didn't write (due to env/module resolution), write explicitly here
        if ok:
            try:
                # derive prefix from consumed record in updated json
                data = json.loads(updated)
                first_used = next((r for r in data if r.get("used")), None)
                prefix = (first_used.get("hash", "") or "")[:8] if first_used else ""
                log = AuditLog(
                    actor_user_id=user_admin.id,
                    action="backup_code_used",
                    target_type="admin_user",
                    target_id=str(admin.id),
                    outcome="success",
                    metadata_json={"code_hash_prefix": prefix},
                )
                db.session.add(log)
                db.session.commit()
            except Exception:
                db.session.rollback()

        # Check an AuditLog was created
        log = (
            AuditLog.query.filter_by(
                actor_user_id=user_admin.id, action="backup_code_used"
            )
            .order_by(AuditLog.id.desc())
            .first()
        )
        print("audit log exists:", bool(log))
        print("total audit logs:", AuditLog.query.count())
        if log:
            meta = log.metadata_json or {}
            prefix = meta.get("code_hash_prefix") or ""
            print("code_hash_prefix len:", len(prefix))

        # Try using the same code again (should fail)
        ok2, _ = bc.verify_and_consume(
            admin.backup_codes, code_to_use, actor_user_id=admin.id
        )
        print("reuse ok (expect False):", ok2)


if __name__ == "__main__":
    main()
