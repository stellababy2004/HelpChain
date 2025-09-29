from fastapi import Depends, HTTPException, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from models import User
from db import get_db  # адаптирай към твоя get_db / session

oauth2_scheme = ...  # ...existing code...


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    try:
        payload = jwt.decode(token, "YOUR_JWT_SECRET", algorithms=["HS256"])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid authentication")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication")
    user = db.query(User).filter_by(id=int(user_id)).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def require_role(*allowed_roles):
    def dependency(current_user: User = Depends(get_current_user)):
        if current_user.role.value not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role"
            )
        return current_user

    return dependency
