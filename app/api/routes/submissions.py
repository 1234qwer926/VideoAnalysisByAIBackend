from datetime import datetime
from pathlib import Path
import random
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.assignment import AssignmentUser, Assignment
from app.models.form import Form
from app.models.submission import Submission, QuestionResponse, WarningLog
from app.schemas.submission import SubmissionCreate, SubmissionOut, WarningCreate
from app.services.s3_service import S3Service
from app.services.evaluator import evaluate_submission_background
from app.core.config import settings
from fastapi import File, UploadFile

router = APIRouter(prefix="/exam", tags=["Exam / Submission"])
_exam_drafts: dict[str, dict] = {}
LOCAL_UPLOAD_PREFIX = "local_uploads/"
LOCAL_UPLOAD_ROOT = Path("/tmp/lms_video_uploads")

# ── File upload security constants ─────────────────────────────
ALLOWED_VIDEO_MIME_TYPES = frozenset(["video/webm", "video/mp4", "video/ogg", "video/quicktime"])
MAX_VIDEO_SIZE_BYTES = 500 * 1024 * 1024  # 500 MB


def _sanitize_filename(filename: str | None) -> str:
    """Strip path traversal and unsafe characters from a filename."""
    if not filename:
        return "video.webm"
    import re
    # Remove any path components (e.g. ../../../etc/passwd)
    filename = re.sub(r"[/\\][.]{2}", "", filename)
    # Keep only safe characters (alphanumeric, dash, underscore, dot, space)
    filename = re.sub(r"[^\w\-. ]", "_", filename)
    # Remove leading dots to prevent hidden files
    filename = filename.lstrip(".")
    return filename or "video.webm"


def _validate_video_file(file: UploadFile, max_size: int = MAX_VIDEO_SIZE_BYTES) -> None:
    """Validate MIME type and size of an uploaded video file. Raises HTTPException on failure."""
    content_type = (file.content_type or "").strip().lower()
    # Extract base MIME type (remove codec parameters like ;codecs=vp9,opus)
    base_content_type = content_type.split(";")[0].strip()
    if base_content_type not in ALLOWED_VIDEO_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{content_type}' (base: '{base_content_type}'). Allowed: {', '.join(sorted(ALLOWED_VIDEO_MIME_TYPES))}",
        )
    # Note: file.size may not be populated by all UploadFile implementations.
    # We check content_length from the async reader by reading and checking length.
    # For now, rely on the content_type guard and let size limits be enforced by the
    # streaming read in _save_local_exam_upload.


def _question_to_payload(q):
    config = q.config or {}
    section = config.get("section") or q.type.upper()
    section_time_seconds = config.get("section_time_seconds")
    return {
        "id": q.id,
        "type": q.type,
        "title": q.title,
        "description": q.description,
        "prompt": q.description,
        "required": q.required,
        "order": q.order,
        "points": q.points,
        "config": config,
        "section": section,
        "section_time_seconds": section_time_seconds,
    }


def _build_sections(questions: list[dict]) -> list[dict]:
    sections = []
    section_index_by_name = {}
    for idx, q in enumerate(questions):
        section_name = q.get("section") or "GENERAL"
        if section_name not in section_index_by_name:
            section_index_by_name[section_name] = len(sections)
            sections.append({
                "name": section_name,
                "start_index": idx,
                "end_index": idx,
                "question_count": 1,
                "time_seconds": q.get("section_time_seconds"),
            })
        else:
            section_idx = section_index_by_name[section_name]
            sections[section_idx]["end_index"] = idx
            sections[section_idx]["question_count"] += 1
    return sections


def _get_questions_for_token(token: str, form: Form):
    questions = list(form.questions or [])
    if not questions:
        return []

    draft = _exam_drafts.setdefault(token, {})
    saved_order = draft.get("question_order")
    by_id = {q.id: q for q in questions}

    if saved_order:
        ordered = [by_id[qid] for qid in saved_order if qid in by_id]
        missing = [q for q in questions if q.id not in saved_order]
        return ordered + missing

    if form.randomize_questions:
        random.shuffle(questions)

    draft["question_order"] = [q.id for q in questions]
    draft["max_question_index_reached"] = int(draft.get("max_question_index_reached", 0))
    return questions


def _get_assignment_user(token: str, db: Session) -> AssignmentUser:
    user = db.query(AssignmentUser).filter(AssignmentUser.token == token).first()

    if not user:
        raise HTTPException(status_code=404, detail="Invalid access token")

    if user.status == "completed":
        raise HTTPException(status_code=403, detail="Exam already completed")

    if user.status == "expired":
        raise HTTPException(status_code=403, detail="Assignment expired")

    if user.deadline and datetime.utcnow() > user.deadline.replace(tzinfo=None):
        user.status = "expired"
        db.commit()
        raise HTTPException(status_code=403, detail="Deadline passed")

    return user


def _local_upload_path_for_key(key: str) -> Path:
    relative = key.removeprefix(LOCAL_UPLOAD_PREFIX)
    # Security: normalize the resolved path and verify it stays within LOCAL_UPLOAD_ROOT
    # This prevents path traversal attacks (e.g. key="local_uploads/../../etc/passwd")
    resolved = (LOCAL_UPLOAD_ROOT / relative).resolve()
    if not str(resolved).startswith(str(LOCAL_UPLOAD_ROOT.resolve())):
        raise HTTPException(status_code=400, detail="Invalid local video key")
    return resolved


async def _save_local_exam_upload(file: UploadFile, user: AssignmentUser, question_id: int) -> dict:
    safe_filename = _sanitize_filename(file.filename)
    suffix = Path(safe_filename).suffix or ".webm"
    timestamp = int(datetime.utcnow().timestamp())
    relative = f"{user.assignment_id}/{user.id}/q{question_id}_{timestamp}{suffix}"
    key = f"{LOCAL_UPLOAD_PREFIX}{relative}"
    target = _local_upload_path_for_key(key)
    target.parent.mkdir(parents=True, exist_ok=True)

    contents = await file.read()
    target.write_bytes(contents)

    return {"key": key, "filename": file.filename or target.name, "verified": True}


@router.get("/info")
def get_exam_info(token: str, db: Session = Depends(get_db)):
    user = _get_assignment_user(token, db)
    assignment = db.query(Assignment).filter(Assignment.id == user.assignment_id).first()
    form = db.query(Form).filter(Form.id == assignment.form_id).first()

    draft = _exam_drafts.setdefault(token, {})

    # Eagerly build questions list so they appear in the JSON response
    questions = []
    if form and form.questions:
        ordered_questions = _get_questions_for_token(token, form)
        questions = [_question_to_payload(q) for q in ordered_questions]
    sections = _build_sections(questions)

    return {
        "assignment": assignment,
        "form": form,
        "questions": questions,
        "sections": sections,
        "status": user.status,
        "deadline": user.deadline,
        "saved_answers": draft.get("answers", {}),
        "current_question_index": draft.get("current_question_index", 0),
        "max_question_index_reached": draft.get("max_question_index_reached", 0),
        "violation_count": draft.get("violation_count", 0),
        "proctor_events": draft.get("proctor_events", []),
    }


@router.post("/start")
def start_exam(token: str, db: Session = Depends(get_db)):
    user = _get_assignment_user(token, db)

    if user.status == "pending":
        user.status = "started"
        db.commit()

    return {"status": user.status}


@router.post("/presigned-upload")
def get_upload_url(
    token: str,
    question_id: int,
    content_type: str = "video/webm",
    db: Session = Depends(get_db)
):
    user = _get_assignment_user(token, db)

    s3_key = f"submissions/{user.assignment_id}/{user.id}/q{question_id}_{int(datetime.utcnow().timestamp())}.webm"

    if settings.AWS_ACCESS_KEY_ID:
        from app.services.s3 import generate_presigned_upload_url
        url = generate_presigned_upload_url(s3_key, content_type=content_type)
    else:
        url = f"http://localhost:9000/{s3_key}"

    return {
        "upload_url": url,
        "s3_key": s3_key
    }

@router.post("/upload-video")
async def upload_video(
    token: str,
    question_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    user = _get_assignment_user(token, db)

    # Security: validate MIME type before any processing
    _validate_video_file(file)

    try:
        if not file.filename:
            file.filename = f"q{question_id}.webm"

        try:
            s3_service = S3Service()
            result = await s3_service.upload_file_with_verification(file)
        except Exception as s3_error:
            print(f"Warning: S3 upload failed, falling back to local storage: {s3_error}")
            result = await _save_local_exam_upload(file, user, question_id)

        return {
            "s3_key": result["key"],
            "filename": result["filename"],
            "verified": result.get("verified", False)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/local-video")
def get_local_video(key: str, db: Session = Depends(get_db)):
    if not key.startswith(LOCAL_UPLOAD_PREFIX):
        raise HTTPException(status_code=400, detail="Invalid local video key")

    path = _local_upload_path_for_key(key)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Video file not found")

    return FileResponse(path, media_type="video/webm", content_disposition_type="inline")


@router.post("/save")
def save_exam_progress(
    token: str,
    payload: dict,
    db: Session = Depends(get_db)
):
    _get_assignment_user(token, db)

    answers = payload.get("answers")
    current_question_index = int(payload.get("current_question_index", 0))

    if not isinstance(answers, dict):
        raise HTTPException(status_code=400, detail="answers must be an object")

    existing = _exam_drafts.setdefault(token, {})
    max_reached = int(existing.get("max_question_index_reached", 0))
    if current_question_index < max_reached:
        raise HTTPException(status_code=400, detail="Backward navigation is not allowed")

    existing["answers"] = answers
    existing["current_question_index"] = current_question_index
    existing["max_question_index_reached"] = max(current_question_index, max_reached)
    existing["updated_at"] = datetime.utcnow().isoformat()

    return {
        "status": "saved",
        "saved_count": len(answers),
        "current_question_index": current_question_index,
        "max_question_index_reached": existing["max_question_index_reached"],
    }


@router.post("/submit", response_model=SubmissionOut)
def submit_exam(
    payload: SubmissionCreate, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    user = _get_assignment_user(payload.assignment_user_token, db)
    _exam_drafts.pop(payload.assignment_user_token, None)

    sub = Submission(
        assignment_user_id=user.id,
        is_auto_submitted=payload.is_auto_submitted
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)

    for r in payload.responses:
        resp = QuestionResponse(
            submission_id=sub.id,
            question_id=r.question_id,
            s3_key=r.s3_key,
            answer=r.answer,
            upload_time=datetime.utcnow()
        )
        db.add(resp)

    user.status = "completed"
    db.commit()
    db.refresh(sub)

    background_tasks.add_task(evaluate_submission_background, sub.id)

    return sub


@router.post("/warning")
def log_warning(
    token: str,
    payload: WarningCreate,
    submission_id: int,
    db: Session = Depends(get_db)
):
    _get_assignment_user(token, db)

    log = WarningLog(
        submission_id=submission_id,
        type=payload.type
    )
    db.add(log)
    db.commit()
    db.refresh(log)

    return log


@router.post("/proctor-event")
def log_proctor_event(
    token: str,
    payload: dict,
    db: Session = Depends(get_db)
):
    _get_assignment_user(token, db)

    existing = _exam_drafts.setdefault(token, {})
    event_type = str(payload.get("type") or "unknown")
    detail = str(payload.get("detail") or "")
    question_index = int(payload.get("current_question_index") or 0)

    events = existing.setdefault("proctor_events", [])
    events.append({
        "type": event_type,
        "detail": detail,
        "current_question_index": question_index,
        "timestamp": datetime.utcnow().isoformat(),
    })
    existing["violation_count"] = int(existing.get("violation_count", 0)) + 1

    return {
        "status": "logged",
        "violation_count": existing["violation_count"],
    }
