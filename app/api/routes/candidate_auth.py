from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.assignment import AssignmentUser
from app.core.security import create_access_token
from app.schemas.candidate import CandidateLogin, CandidateToken
from app.core.config import settings
from app.core.rate_limit import limiter, LOGIN_RATE_LIMIT, GOOGLE_LOGIN_RATE_LIMIT
from pydantic import BaseModel
from google.oauth2 import id_token
from google.auth.transport import requests
import os
from dotenv import load_dotenv

load_dotenv()

class GoogleAuthRequest(BaseModel):
    token: str

router = APIRouter(prefix="/candidate/auth", tags=["Candidate Auth"])

@router.post("/login", response_model=CandidateToken)
@limiter.limit(LOGIN_RATE_LIMIT)
def candidate_login(request: Request, payload: CandidateLogin, db: Session = Depends(get_db)):
    exists = db.query(AssignmentUser).filter(
        AssignmentUser.email == payload.email
    ).first()
    if not exists:
        raise HTTPException(status_code=404, detail="No assignment found for this email")
    token = create_access_token({"sub": payload.email, "role": "candidate"})
    return CandidateToken(access_token=token)

@router.post("/google-login", response_model=CandidateToken)
@limiter.limit(GOOGLE_LOGIN_RATE_LIMIT)
def candidate_google_login(request: Request, payload: GoogleAuthRequest, db: Session = Depends(get_db)):
    try:
        client_id = os.environ.get("GOOGLE_CLIENT_ID") or settings.GOOGLE_CLIENT_ID
        if not client_id:
            raise HTTPException(status_code=500, detail="Google Client ID not configured")
            
        idinfo = id_token.verify_oauth2_token(payload.token, requests.Request(), client_id)
        email = idinfo.get("email")
        
        if not email:
            raise HTTPException(status_code=400, detail="Email not found in Google token")
            
        exists = db.query(AssignmentUser).filter(
            AssignmentUser.email == email
        ).first()
        
        if not exists:
            raise HTTPException(status_code=403, detail="No assignment found for this email")
            
        token = create_access_token({"sub": email, "role": "candidate"})
        
        # Get user info from Google token
        user_info = {
            "email": email,
            "name": idinfo.get("name", ""),
            "picture": idinfo.get("picture", ""),
            "given_name": idinfo.get("given_name", ""),
            "family_name": idinfo.get("family_name", ""),
        }
        
        return CandidateToken(access_token=token, user=user_info)
        
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid Google token")


# ── Set HttpOnly Session Cookie ────────────────────────────────
@router.post("/set-session-cookie")
@limiter.limit("60/minute")
async def set_session_cookie(request: Request, response: Response):
    body = await request.json()
    token = body.get("token")
    if not token:
        raise HTTPException(status_code=400, detail="token is required")

    response.set_cookie(
        key="candidate_session_token",
        value=token,
        httponly=True,
        samesite="strict",
        secure=(settings.ENV == "production"),
        max_age=60 * 60 * settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        path="/",
    )
    return {"message": "Session cookie set"}