# ruff: noqa
from audit import log_admin_action
from db import get_db
from dependencies import require_role
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.models import User

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/requests/{request_id}/approve")
def approve_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("admin", "superadmin", "moderator")),
):
    # TODO: реализирай логиката за одобрение на заявка
    # пример: mark request approved...
    log_admin_action(
        db,
        current_user.id,
        "approve_request",
        target_type="request",
        target_id=str(request_id),
        outcome="approved",
    )
    return {"status": "approved"}


@router.post("/requests/{request_id}/reject")
def reject_request(
    request_id: int,
    reason: str = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("admin", "superadmin", "moderator")),
):
    # TODO: реализирай логика за отхвърляне
    log_admin_action(
        db,
        current_user.id,
        "reject_request",
        target_type="request",
        target_id=str(request_id),
        outcome="rejected",
        metadata={"reason": reason},
    )
    return {"status": "rejected"}


@router.post("/users/{user_id}/role")
def change_user_role(
    user_id: int,
    new_role: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("superadmin")),
):
    user = db.query(User).filter_by(id=user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if new_role not in [r.value for r in User.__table__.c.role.type.enums]:
        # safe check; alternatively use RoleEnum
        pass
    user.role = new_role
    db.add(user)
    db.commit()
    log_admin_action(
        db,
        current_user.id,
        "change_role",
        target_type="user",
        target_id=str(user_id),
        outcome="role_changed",
        metadata={"new_role": new_role},
    )
    return {"status": "ok", "new_role": new_role}
