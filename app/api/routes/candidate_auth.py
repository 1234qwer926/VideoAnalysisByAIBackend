from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.assignment import AssignmentUser
from app.core.security import create_access_token
from app.schemas.candidate import CandidateLogin, CandidateToken

router = APIRouter(prefix="/candidate/auth", tags=["Candidate Auth"])

@router.post("/login", response_model=CandidateToken)
def candidate_login(payload: CandidateLogin, db: Session = Depends(get_db)):
    exists = db.query(AssignmentUser).filter(
        AssignmentUser.email == payload.email
    ).first()
    if not exists:
        raise HTTPException(status_code=404, detail="No assignment found for this email")
    token = create_access_token({"sub": payload.email, "role": "candidate"})
    return CandidateToken(access_token=token)