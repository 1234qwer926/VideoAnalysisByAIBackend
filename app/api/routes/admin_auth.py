from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.admin import Admin
from app.core.security import verify_password, create_access_token, hash_password
from app.schemas.admin import AdminLogin, Token, AdminOut

router = APIRouter(prefix="/admin/auth", tags=["Admin Auth"])

@router.post("/login", response_model=Token)
def login(payload: AdminLogin, db: Session = Depends(get_db)):
    admin = db.query(Admin).filter(Admin.email == payload.email).first()
    if not admin or not verify_password(payload.password, admin.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": admin.email, "role": "admin"})
    return Token(access_token=token)


@router.post("/register", response_model=AdminOut)
def register(payload: AdminLogin, db: Session = Depends(get_db)):
    if db.query(Admin).filter(Admin.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    admin = Admin(
        email=payload.email,
        hashed_password=hash_password(payload.password)
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin
