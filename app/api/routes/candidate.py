from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.assignment import AssignmentUser, Assignment
from app.models.submission import Submission, QuestionResponse
from app.models.review import Review
from app.models.form import Question
from app.core.security import decode_token

router = APIRouter(prefix="/candidate", tags=["Candidate"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/candidate/auth/login")


def _get_candidate_email(token: str = Depends(oauth2_scheme)) -> str:
    try:
        payload = decode_token(token)
        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=401, detail="Invalid token")
        return email
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.get("/dashboard")
def candidate_dashboard(
    email: str = Depends(_get_candidate_email),
    db: Session = Depends(get_db)
):
    users = db.query(AssignmentUser).filter(
        AssignmentUser.email == email
    ).all()

    result = []

    for u in users:
        assignment = db.query(Assignment).filter(
            Assignment.id == u.assignment_id
        ).first()

        sub = db.query(Submission).filter(
            Submission.assignment_user_id == u.id
        ).first()

        review = None
        if sub:
            review = db.query(Review).filter(
                Review.submission_id == sub.id
            ).first()

        result.append({
            "id": sub.id if sub else None,
            "assignment_id": u.assignment_id,
            "assignment_title": assignment.title if assignment else "",
            "description": assignment.description if assignment else "",
            "status": u.status,
            "deadline": u.deadline,
            "token": u.token,
            "submission_id": sub.id if sub else None,
            "score": review.final_score if review else None,
        })

    return result


@router.get("/assignments")
def candidate_assignments(
    email: str = Depends(_get_candidate_email),
    db: Session = Depends(get_db)
):
    return candidate_dashboard(email, db)


@router.get("/results")
def candidate_results(
    email: str = Depends(_get_candidate_email),
    db: Session = Depends(get_db)
):
    rows = candidate_dashboard(email, db)
    return [r for r in rows if r.get("submission_id") is not None]


@router.get("/results/{result_id}")
def candidate_result_detail(
    result_id: int,
    email: str = Depends(_get_candidate_email),
    db: Session = Depends(get_db)
):
    sub = db.query(Submission).filter(Submission.id == result_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Result not found")

    assignment_user = db.query(AssignmentUser).filter(
        AssignmentUser.id == sub.assignment_user_id
    ).first()
    if not assignment_user or assignment_user.email != email:
        raise HTTPException(status_code=403, detail="Forbidden")

    assignment = db.query(Assignment).filter(Assignment.id == assignment_user.assignment_id).first()
    review = db.query(Review).filter(Review.submission_id == sub.id).first()
    responses = db.query(QuestionResponse).filter(QuestionResponse.submission_id == sub.id).all()

    # Build per-question detail with question title and description
    enriched_responses = []
    for r in responses:
        question = db.query(Question).filter(Question.id == r.question_id).first()
        enriched_responses.append({
            "id": r.id,
            "question_id": r.question_id,
            "question_title": question.title if question else f"Question {r.question_id}",
            "question_description": question.description if question else "",
            "question_type": question.type if question else "text",
            "answer": r.answer,
        })

    return {
        "id": sub.id,
        "assignment_title": assignment.title if assignment else "Assessment",
        "status": assignment_user.status,
        "submitted_at": sub.submitted_at,
        "final_score": review.final_score if review else None,
        "feedback": review.comments if review else "",
        "responses": enriched_responses,
    }
