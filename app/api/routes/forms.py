from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.db.database import get_db
from app.models.form import Form, Question
from app.schemas.form import FormCreate, FormUpdate, FormOut, QuestionCreate, QuestionOut, QuestionUpsert
from app.core.deps import get_current_admin

router = APIRouter(prefix="/admin/forms", tags=["Forms"])


def _question_payload_to_model_data(question: QuestionUpsert) -> dict:
    options = [opt for opt in (question.options or []) if str(opt).strip()]
    config = {"options": options} if options else {}
    if question.section:
        config["section"] = question.section
    if question.section_time_seconds and question.section_time_seconds > 0:
        config["section_time_seconds"] = question.section_time_seconds
    return {
        "type": question.type,
        "title": question.title,
        "description": question.prompt,
        "required": question.required,
        "order": question.order,
        "points": question.points,
        "config": config,
    }


def _sync_form_questions(form: Form, questions: List[QuestionUpsert], db: Session) -> None:
    existing_by_id = {q.id: q for q in form.questions}
    incoming_ids = set()

    for index, question in enumerate(questions):
        model_data = _question_payload_to_model_data(question)
        model_data["order"] = index

        if question.id and question.id in existing_by_id:
            incoming_ids.add(question.id)
            existing = existing_by_id[question.id]
            for key, value in model_data.items():
                setattr(existing, key, value)
        else:
            db.add(Question(form_id=form.id, **model_data))

    # Keep only questions present in the current payload.
    for existing in list(form.questions):
        if existing.id not in incoming_ids:
            db.delete(existing)


@router.get("/", response_model=List[FormOut])
def list_forms(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    return db.query(Form).order_by(Form.id.desc()).all()


@router.post("/", response_model=FormOut)
def create_form(payload: FormCreate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    form_data = payload.model_dump(exclude={"questions", "category"})
    form = Form(**form_data)
    db.add(form)
    db.flush()
    _sync_form_questions(form, payload.questions or [], db)
    db.commit()
    db.refresh(form)
    return form


@router.get("/{form_id}", response_model=FormOut)
def get_form(form_id: int, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    form = db.query(Form).filter(Form.id == form_id).first()
    if not form:
        raise HTTPException(404, "Form not found")
    return form


@router.put("/{form_id}", response_model=FormOut)
def update_form(form_id: int, payload: FormUpdate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    form = db.query(Form).filter(Form.id == form_id).first()
    if not form:
        raise HTTPException(404, "Form not found")
    updates = payload.model_dump(exclude_unset=True, exclude={"questions", "category"})
    for k, v in updates.items():
        setattr(form, k, v)
    if payload.questions is not None:
        _sync_form_questions(form, payload.questions, db)
    db.commit()
    db.refresh(form)
    return form


@router.delete("/{form_id}", status_code=204)
def delete_form(form_id: int, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    form = db.query(Form).filter(Form.id == form_id).first()
    if not form:
        raise HTTPException(404, "Form not found")
    db.delete(form)
    db.commit()


@router.post("/{form_id}/questions", response_model=QuestionOut)
def add_question(form_id: int, payload: QuestionCreate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    form = db.query(Form).filter(Form.id == form_id).first()
    if not form:
        raise HTTPException(404, "Form not found")
    q = Question(form_id=form_id, **payload.model_dump())
    db.add(q)
    db.commit()
    db.refresh(q)
    return q


@router.put("/{form_id}/questions/reorder", status_code=200)
def reorder_questions(form_id: int, order: List[dict], db: Session = Depends(get_db), _=Depends(get_current_admin)):
    for item in order:
        db.query(Question).filter(
            Question.id == item["id"],
            Question.form_id == form_id
        ).update({"order": item["order"]})
    db.commit()
    return {"status": "ok"}


@router.put("/{form_id}/questions/{q_id}", response_model=QuestionOut)
def update_question(form_id: int, q_id: int, payload: QuestionCreate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    q = db.query(Question).filter(
        Question.id == q_id,
        Question.form_id == form_id
    ).first()
    if not q:
        raise HTTPException(404, "Question not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(q, k, v)
    db.commit()
    db.refresh(q)
    return q


@router.delete("/{form_id}/questions/{q_id}", status_code=204)
def delete_question(form_id: int, q_id: int, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    q = db.query(Question).filter(
        Question.id == q_id,
        Question.form_id == form_id
    ).first()
    if not q:
        raise HTTPException(404, "Question not found")
    db.delete(q)
    db.commit()
