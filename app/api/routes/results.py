from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.assignment import AssignmentUser, Assignment
from app.models.submission import Submission, QuestionResponse, WarningLog
from app.models.review import Review
from app.schemas.review import ReviewUpdate, ReviewOut
from app.core.deps import get_current_admin
from app.services.s3 import generate_presigned_view_url
from app.core.config import settings

router = APIRouter(prefix="/admin/results", tags=["Results"])


@router.get("")
def list_results(
    db: Session = Depends(get_db),
    _=Depends(get_current_admin)
):
    users = db.query(AssignmentUser).all()
    rows = []
    for u in users:
        assignment = db.query(Assignment).filter(Assignment.id == u.assignment_id).first()
        sub = db.query(Submission).filter(Submission.assignment_user_id == u.id).first()
        review = db.query(Review).filter(Review.submission_id == sub.id).first() if sub else None
        rows.append({
            "id": sub.id if sub else u.id,
            "submission_id": sub.id if sub else None,
            "candidate_email": u.email,
            "assignment_title": assignment.title if assignment else "",
            "assignment_id": u.assignment_id,
            "user_id": u.id,
            "status": u.status,
            "submitted_at": sub.submitted_at if sub else None,
            "final_score": review.final_score if review else None,
        })
    return rows


@router.get("/{assignment_id}")
def get_assignment_results(
    assignment_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin)
):
    users = db.query(AssignmentUser).filter(
        AssignmentUser.assignment_id == assignment_id
    ).all()

    result = []

    for u in users:
        sub = db.query(Submission).filter(
            Submission.assignment_user_id == u.id
        ).first()

        warning_count = 0
        if sub:
            warning_count = db.query(WarningLog).filter(
                WarningLog.submission_id == sub.id
            ).count()

        result.append({
            "user_id": u.id,
            "email": u.email,
            "deadline": u.deadline,
            "status": u.status,
            "submitted_at": sub.submitted_at if sub else None,
            "warning_count": warning_count,
            "submission_id": sub.id if sub else None,
        })

    return result


@router.get("/submission/{submission_id}")
def get_submission_detail(
    submission_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin)
):
    sub = db.query(Submission).filter(Submission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")

    assignment_user = db.query(AssignmentUser).filter(
        AssignmentUser.id == sub.assignment_user_id
    ).first()
    assignment = None
    if assignment_user:
        assignment = db.query(Assignment).filter(Assignment.id == assignment_user.assignment_id).first()

    responses = db.query(QuestionResponse).filter(
        QuestionResponse.submission_id == submission_id
    ).all()

    warnings = db.query(WarningLog).filter(
        WarningLog.submission_id == submission_id
    ).all()

    review = db.query(Review).filter(
        Review.submission_id == submission_id
    ).first()

    enriched = []
    for r in responses:
        video_url = None
        if r.s3_key:
            if settings.AWS_ACCESS_KEY_ID:
                video_url = generate_presigned_view_url(r.s3_key)
            else:
                video_url = f"http://localhost:9000/{r.s3_key}"

        enriched.append({
            "id": r.id,
            "submission_id": r.submission_id,
            "question_id": r.question_id,
            "s3_key": r.s3_key,
            "answer": r.answer,
            "upload_time": r.upload_time,
            "video_url": video_url,
            "score": r.score,
        })

    return {
        "id": sub.id,
        "candidate_email": assignment_user.email if assignment_user else "",
        "assignment_title": assignment.title if assignment else "",
        "status": assignment_user.status if assignment_user else "submitted",
        "submitted_at": sub.submitted_at,
        "final_score": review.final_score if review else None,
        "feedback": review.comments if review else "",
        "submission": {
            "id": sub.id,
            "assignment_user_id": sub.assignment_user_id,
            "submitted_at": sub.submitted_at,
            "is_auto_submitted": sub.is_auto_submitted,
        },
        "responses": enriched,
        "warnings": [
            {
                "id": w.id,
                "type": w.type,
                "timestamp": w.timestamp
            } for w in warnings
        ],
        "review": {
            "id": review.id,
            "submission_id": review.submission_id,
            "ai_score": review.ai_score,
            "admin_score": review.admin_score,
            "final_score": review.final_score,
            "comments": review.comments,
        } if review else None,
    }


@router.put("/submission/{submission_id}/review", response_model=ReviewOut)
def upsert_review(
    submission_id: int,
    payload: ReviewUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin)
):
    review = db.query(Review).filter(
        Review.submission_id == submission_id
    ).first()

    if not review:
        review = Review(submission_id=submission_id)
        db.add(review)

    for k, v in payload.model_dump(exclude_unset=True).items():
        if k == "question_scores" and v is not None:
            for r_id, q_score in v.items():
                resp = db.query(QuestionResponse).filter(QuestionResponse.id == int(r_id)).first()
                if resp:
                    resp.score = q_score
            continue
        setattr(review, k, v)

    db.commit()
    db.refresh(review)

    return review


@router.put("/{result_id}", response_model=ReviewOut)
def update_result_review(
    result_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin)
):
    mapped = ReviewUpdate(
        final_score=payload.get("score"),
        comments=payload.get("feedback"),
        question_scores=payload.get("question_scores")
    )
    return upsert_review(result_id, mapped, db, _)
