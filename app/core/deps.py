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
    # SECURITY: Explicitly reject ENABLE_DEV_ADMIN_BYPASS unless ENV is explicitly "development"
    # This prevents the bypass from activating if ENV is misconfigured to any other value
    # (including empty string, "prod", "production", etc.)
    if settings.ENABLE_DEV_ADMIN_BYPASS:
        if settings.ENV != "development":
            raise HTTPException(
                status_code=403,
                detail="Dev admin bypass is only allowed when ENV=development"
            )
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
