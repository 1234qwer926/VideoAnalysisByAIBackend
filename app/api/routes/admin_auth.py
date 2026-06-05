from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import secrets
import os

from app.db.database import get_db
from app.models.admin import Admin
from app.core.security import verify_password, create_access_token, hash_password
from app.core.deps import get_current_admin
from app.core.config import settings
from app.schemas.admin import (
    AdminLogin, Token, AdminOut,
    GoogleAuthRequest, ForgotPasswordRequest, ResetPasswordRequest,
)
from app.services.email import send_password_reset_email

from google.oauth2 import id_token
from google.auth.transport import requests
from dotenv import load_dotenv

load_dotenv()

router = APIRouter(prefix="/admin/auth", tags=["Admin Auth"])


# ── Email + Password Login ──────────────────────────────────────
@router.post("/login", response_model=Token)
def login(payload: AdminLogin, db: Session = Depends(get_db)):
    admin = db.query(Admin).filter(Admin.email == payload.email).first()
    if not admin or not verify_password(payload.password, admin.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": admin.email, "role": "admin"})
    return Token(access_token=token)


# ── Google OAuth Login ──────────────────────────────────────────
@router.post("/google-login", response_model=Token)
def admin_google_login(payload: GoogleAuthRequest, db: Session = Depends(get_db)):
    try:
        client_id = os.environ.get("GOOGLE_CLIENT_ID") or settings.GOOGLE_CLIENT_ID
        if not client_id:
            raise HTTPException(status_code=500, detail="Google Client ID not configured")

        idinfo = id_token.verify_oauth2_token(
            payload.token, requests.Request(), client_id
        )
        email = idinfo.get("email")

        if not email:
            raise HTTPException(status_code=400, detail="Email not found in Google token")

        admin = db.query(Admin).filter(Admin.email == email).first()
        if not admin:
            raise HTTPException(
                status_code=403,
                detail="No admin account found for this email. Contact a super admin.",
            )

        token = create_access_token({"sub": email, "role": "admin"})
        return Token(access_token=token)

    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid Google token")


# ── Forgot Password ────────────────────────────────────────────
@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    admin = db.query(Admin).filter(Admin.email == payload.email).first()

    # Always return success to avoid email enumeration
    if not admin:
        return {"message": "If the email exists, a reset link has been sent."}

    # Generate a secure token valid for 30 minutes
    reset_token = secrets.token_urlsafe(48)
    admin.reset_token = reset_token
    admin.reset_token_expires = datetime.utcnow() + timedelta(minutes=30)
    db.commit()

    # Build the reset URL
    frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:5173")
    reset_link = f"{frontend_url}/admin/reset-password?token={reset_token}"

    try:
        send_password_reset_email(admin.email, reset_link)
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send password reset: {e}")
        # In development, still print the link
        print(f"[DEV] Reset link: {reset_link}")

    return {"message": "If the email exists, a reset link has been sent."}


# ── Reset Password ──────────────────────────────────────────────
@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    admin = db.query(Admin).filter(Admin.reset_token == payload.token).first()

    if not admin:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    if not admin.reset_token_expires or admin.reset_token_expires < datetime.utcnow():
        # Clear the expired token
        admin.reset_token = None
        admin.reset_token_expires = None
        db.commit()
        raise HTTPException(status_code=400, detail="Reset token has expired. Please request a new one.")

    if len(payload.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    admin.hashed_password = hash_password(payload.new_password)
    admin.reset_token = None
    admin.reset_token_expires = None
    db.commit()

    return {"message": "Password has been reset successfully"}


# ── Register (Protected — requires existing admin) ──────────────
@router.post("/register", response_model=AdminOut)
def register(
    payload: AdminLogin,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    if db.query(Admin).filter(Admin.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    admin = Admin(
        email=payload.email,
        hashed_password=hash_password(payload.password),
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin
