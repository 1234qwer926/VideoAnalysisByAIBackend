import secrets
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.db.database import get_db
from app.models.assignment import Assignment, AssignmentUser
from app.schemas.assignment import (
    AssignmentCreate, AssignmentOut,
    AssignmentUserCreate, AssignmentUserBulk, AssignmentUserOut
)
from app.core.deps import get_current_admin
from app.services.email import send_assignment_email

router = APIRouter(prefix="/admin/assignments", tags=["Assignments"])

@router.get("/", response_model=List[AssignmentOut])
def list_assignments(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    return db.query(Assignment).order_by(Assignment.id.desc()).all()

@router.post("/", response_model=AssignmentOut)
def create_assignment(payload: AssignmentCreate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    obj = Assignment(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

@router.get("/{assignment_id}", response_model=AssignmentOut)
def get_assignment(assignment_id: int, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    obj = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not obj:
        raise HTTPException(404, "Assignment not found")
    return obj

@router.put("/{assignment_id}", response_model=AssignmentOut)
def update_assignment(assignment_id: int, payload: AssignmentCreate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    obj = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not obj:
        raise HTTPException(404, "Assignment not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj

@router.delete("/{assignment_id}", status_code=204)
def delete_assignment(assignment_id: int, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    obj = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not obj:
        raise HTTPException(404, "Assignment not found")
    db.delete(obj)
    db.commit()

# ── User Management ──────────────────────────────────────────────────────────

@router.get("/{assignment_id}/users", response_model=List[AssignmentUserOut])
def list_users(assignment_id: int, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    return db.query(AssignmentUser).filter(
        AssignmentUser.assignment_id == assignment_id
    ).all()

@router.post("/{assignment_id}/users", response_model=AssignmentUserOut)
def add_user(assignment_id: int, payload: AssignmentUserCreate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(404, "Assignment not found")

    existing = db.query(AssignmentUser).filter(
        AssignmentUser.assignment_id == assignment_id,
        AssignmentUser.email == payload.email
    ).first()
    if existing:
        raise HTTPException(400, "Candidate already assigned")

    token = secrets.token_urlsafe(32)
    user = AssignmentUser(
        assignment_id=assignment_id,
        token=token,
        deadline=payload.deadline or assignment.end_date,
        **payload.model_dump(exclude={"deadline"})
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@router.post("/{assignment_id}/users/bulk", response_model=List[AssignmentUserOut])
def add_users_bulk(assignment_id: int, payload: AssignmentUserBulk, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    created = []
    for entry in payload.entries:
        token = secrets.token_urlsafe(32)
        user = AssignmentUser(
            assignment_id=assignment_id,
            token=token,
            **entry.model_dump()
        )
        db.add(user)
        created.append(user)
    db.commit()
    for u in created:
        db.refresh(u)
    return created

@router.post("/{assignment_id}/users/{user_id}/send-email", status_code=200)
def send_email(
    assignment_id: int,
    user_id: int,
    base_url: str = "http://localhost:5173",
    db: Session = Depends(get_db),
    _=Depends(get_current_admin)
):
    user = db.query(AssignmentUser).filter(
        AssignmentUser.id == user_id,
        AssignmentUser.assignment_id == assignment_id
    ).first()
    if not user:
        raise HTTPException(404, "User not found")
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    access_url = f"{base_url}/exam?token={user.token}"
    send_assignment_email(user.email, assignment.title, str(user.deadline), access_url)
    user.email_sent = True
    db.commit()
    return {"status": "sent", "link": access_url}


@router.post("/{assignment_id}/users/{user_id}/resend", status_code=200)
def resend_email(
    assignment_id: int,
    user_id: int,
    base_url: str = "http://localhost:5173",
    db: Session = Depends(get_db),
    _=Depends(get_current_admin)
):
    return send_email(assignment_id, user_id, base_url, db, _)


@router.delete("/{assignment_id}/users/{user_id}", status_code=204)
def delete_user(
    assignment_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin)
):
    """Delete a user assignment"""
    user = db.query(AssignmentUser).filter(
        AssignmentUser.id == user_id,
        AssignmentUser.assignment_id == assignment_id
    ).first()
    if not user:
        raise HTTPException(404, "User not found")
    db.delete(user)
    db.commit()
    return None
