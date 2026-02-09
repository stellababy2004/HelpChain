import base64
import io

import qrcode
from db import get_db
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from audit import log_admin_action
from auth_2fa import disable_2fa, generate_2fa_secret_for_user, verify_2fa_token
from dependencies import get_current_user

router = APIRouter(prefix="/2fa", tags=["2fa"])


@router.post("/setup")
def setup_2fa(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    secret, uri = generate_2fa_secret_for_user(current_user)
    db.add(current_user)
    db.commit()
    # return provisioning uri and data-uri QR to show in UI
    buf = io.BytesIO()
    qrcode.make(uri).save(buf, format="PNG")
    data_uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    return {"provisioning_uri": uri, "qr_data_uri": data_uri}


@router.post("/verify")
def verify_2fa(
    token: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)
):
    ok = verify_2fa_token(current_user, token)
    log_admin_action(
        db, current_user.id, "2fa_verify", outcome="success" if ok else "failure"
    )
    if not ok:
        raise HTTPException(status_code=400, detail="Invalid 2FA token")
    return {"verified": True}


@router.post("/disable")
def disable_2fa_route(
    db: Session = Depends(get_db), current_user=Depends(get_current_user)
):
    disable_2fa(current_user)
    db.add(current_user)
    db.commit()
    log_admin_action(db, current_user.id, "2fa_disabled", outcome="disabled")
    return {"disabled": True}
