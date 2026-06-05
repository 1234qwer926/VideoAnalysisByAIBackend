import json

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.assignment import AssignmentUser, Assignment
from app.models.submission import Submission, QuestionResponse, WarningLog
from app.models.form import Question
from app.models.review import Review
from app.schemas.review import ReviewUpdate, ReviewOut
from app.core.deps import get_current_admin
from app.services.s3_service import S3Service
from app.core.config import settings

router = APIRouter(prefix="/admin/results", tags=["Results"])
REVIEW_META_MARKER = "\n\n---REVIEW_META---\n"


def _split_review_comments(raw_comments: str | None) -> tuple[str, dict]:
    if not raw_comments:
        return "", {}

    if REVIEW_META_MARKER not in raw_comments:
        return raw_comments, {}

    feedback, raw_meta = raw_comments.split(REVIEW_META_MARKER, 1)
    try:
        return feedback, json.loads(raw_meta.strip())
    except json.JSONDecodeError:
        return raw_comments, {}


def _combine_review_comments(feedback: str | None, meta: dict) -> str:
    feedback_text = (feedback or "").strip()
    clean_meta = {k: v for k, v in meta.items() if v not in (None, {}, [], "")}
    if not clean_meta:
        return feedback_text
    return f"{feedback_text}{REVIEW_META_MARKER}{json.dumps(clean_meta, ensure_ascii=False)}"


def _normalize_metric_value(value):
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def _average_metric_dicts(metric_dicts: list[dict]) -> dict:
    totals = {}
    counts = {}
    for metrics in metric_dicts:
        if not isinstance(metrics, dict):
            continue
        for key, value in metrics.items():
            parsed = _normalize_metric_value(value)
            if parsed is None:
                continue
            totals[key] = totals.get(key, 0.0) + parsed
            counts[key] = counts.get(key, 0) + 1

    return {
        key: round(totals[key] / counts[key], 2)
        for key in sorted(totals.keys())
        if counts.get(key)
    }


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
    request: Request,
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
    question_map = {}
    if assignment:
        question_map = {
            q.id: q
            for q in db.query(Question).filter(Question.form_id == assignment.form_id).all()
        }

    responses = db.query(QuestionResponse).filter(
        QuestionResponse.submission_id == submission_id
    ).all()

    warnings = db.query(WarningLog).filter(
        WarningLog.submission_id == submission_id
    ).all()

    review = db.query(Review).filter(
        Review.submission_id == submission_id
    ).first()
    review_feedback, review_meta = _split_review_comments(review.comments if review else "")
    overall_metrics_override = review_meta.get("overall_metrics_override") or {}

    enriched = []
    base_url = str(request.base_url).rstrip("/")
    ai_metric_dicts = []
    final_metric_dicts = []
    total_points = 0.0
    total_ai_score = 0.0
    total_final_score = 0.0
    for r in responses:
        question = question_map.get(r.question_id)
        answer_obj = r.answer if isinstance(r.answer, dict) else {}
        ai_metrics = answer_obj.get("ai_metrics") if isinstance(answer_obj, dict) else None
        ai_feedback = answer_obj.get("ai_feedback") if isinstance(answer_obj, dict) else None
        ai_score = _normalize_metric_value(answer_obj.get("ai_score")) if isinstance(answer_obj, dict) else None
        final_score = _normalize_metric_value(answer_obj.get("final_score")) if isinstance(answer_obj, dict) else None
        if ai_score is None:
            ai_score = _normalize_metric_value(r.score)
        if final_score is None:
            final_score = _normalize_metric_value(r.score)

        final_metrics = ai_metrics or {}
        if isinstance(answer_obj, dict) and isinstance(answer_obj.get("admin_metrics_override"), dict):
            final_metrics = {
                **(ai_metrics or {}),
                **{
                    k: v for k, v in answer_obj.get("admin_metrics_override", {}).items()
                    if _normalize_metric_value(v) is not None
                },
            }

        video_url = None
        if r.s3_key:
            if r.s3_key.startswith("local_uploads/"):
                video_url = f"{base_url}/api/exam/local-video?key={r.s3_key}"
            elif settings.AWS_ACCESS_KEY_ID:
                video_url = S3Service().get_presigned_url(r.s3_key)
            else:
                video_url = f"http://localhost:9000/{r.s3_key}"

        if ai_metrics:
            ai_metric_dicts.append(ai_metrics)
        if final_metrics:
            final_metric_dicts.append(final_metrics)
        question_points = float(question.points or 0) if question else 0.0
        total_points += question_points
        total_ai_score += float(ai_score or 0.0)
        total_final_score += float(final_score or 0.0)

        enriched.append({
            "id": r.id,
            "submission_id": r.submission_id,
            "question_id": r.question_id,
            "question_title": question.title if question else f"Question {r.question_id}",
            "question_description": question.description if question else "",
            "question_type": question.type if question else "text",
            "question_points": question_points,
            "s3_key": r.s3_key,
            "answer": r.answer,
            "upload_time": r.upload_time,
            "video_url": video_url,
            "score": r.score,
            "ai_score": ai_score,
            "final_score": final_score,
            "ai_metrics": ai_metrics or {},
            "final_metrics": final_metrics or {},
            "ai_feedback": ai_feedback or "",
        })

    overall_ai_metrics = _average_metric_dicts(ai_metric_dicts)
    overall_final_metrics = _average_metric_dicts(final_metric_dicts) or dict(overall_ai_metrics)
    overall_final_metrics.update(
        {
            k: v for k, v in overall_metrics_override.items()
            if _normalize_metric_value(v) is not None
        }
    )
    ai_total_percentage = round((total_ai_score / total_points) * 100, 2) if total_points > 0 else None
    final_total_percentage = round((total_final_score / total_points) * 100, 2) if total_points > 0 else None

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
            "feedback_text": review_feedback,
            "overall_metrics_override": overall_metrics_override,
        } if review else None,
        "score_summary": {
            "max_points": round(total_points, 2),
            "ai_points": round(total_ai_score, 2),
            "final_points": round(total_final_score, 2),
            "ai_percentage": ai_total_percentage,
            "final_percentage": final_total_percentage,
        },
        "overall_metrics": {
            "ai": overall_ai_metrics,
            "final": overall_final_metrics,
        },
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
                    answer_obj = resp.answer if isinstance(resp.answer, dict) else {}
                    existing_score = answer_obj.get("ai_score")
                    if existing_score is None and resp.score is not None:
                        answer_obj["ai_score"] = resp.score
                    answer_obj["final_score"] = q_score
                    resp.answer = answer_obj
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
    existing_review = db.query(Review).filter(Review.submission_id == result_id).first()
    _, existing_meta = _split_review_comments(existing_review.comments if existing_review else "")
    feedback_text = payload.get("feedback")
    combined_comments = _combine_review_comments(
        feedback_text,
        {
            **existing_meta,
            "overall_metrics_override": payload.get("overall_metrics_override") or existing_meta.get("overall_metrics_override"),
        },
    )
    mapped = ReviewUpdate(
        final_score=payload.get("score"),
        comments=combined_comments,
        question_scores=payload.get("question_scores")
    )
    return upsert_review(result_id, mapped, db, _)
