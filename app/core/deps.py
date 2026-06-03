from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError
from app.db.database import get_db
from app.core.security import decode_token, hash_password
from app.core.config import settings
from app.models.admin import Admin

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/admin/auth/login")

def get_current_admin(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> Admin:
    # Optional explicit dev bypass.
    if settings.ENV == "development" and settings.ENABLE_DEV_ADMIN_BYPASS:
        email = token
        admin = db.query(Admin).filter(Admin.email == email).first()
        if not admin:
            admin = Admin(
                email=email,
                hashed_password=hash_password("devpassword")
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)
        return admin

    # PRODUCTION — real JWT validation
    try:
        payload = decode_token(token)
        email: str = payload.get("sub")
        role: str = payload.get("role")
        if not email:
            raise HTTPException(status_code=401, detail="Invalid token")
        if role != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")
        admin = db.query(Admin).filter(Admin.email == email).first()
        if not admin:
            raise HTTPException(status_code=401, detail="Admin not found")
        return admin
    except JWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")
