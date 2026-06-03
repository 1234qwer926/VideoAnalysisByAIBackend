import os
import sys
from datetime import datetime, timedelta, timezone
import secrets

CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from app.db.database import Base
from app.core.security import hash_password
from app.models.admin import Admin
from app.models.form import Form, Question
from app.models.assignment import Assignment, AssignmentUser


ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "Admin@12345"
CANDIDATE_EMAIL = "candidate@example.com"


def get_database_url() -> str:
    if "--local" in sys.argv:
        return "sqlite:///./seed_test_logins.db"
    return os.getenv("DATABASE_URL", "")


def seed():
    database_url = get_database_url()
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set. Pass --local or export DATABASE_URL.")

    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine = create_engine(database_url, connect_args=connect_args)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        admin = db.query(Admin).filter(Admin.email == ADMIN_EMAIL).first()
        if not admin:
            admin = Admin(email=ADMIN_EMAIL, hashed_password=hash_password(ADMIN_PASSWORD))
            db.add(admin)
            db.commit()
            db.refresh(admin)

        form = db.query(Form).filter(Form.title == "E2E Test Form").first()
        if not form:
            form = Form(
                title="E2E Test Form",
                description="Form for end-to-end login/flow testing",
                instructions="Answer all questions",
                is_published=True,
            )
            db.add(form)
            db.commit()
            db.refresh(form)

            q = Question(
                form_id=form.id,
                type="short_text",
                title="Introduce yourself",
                description="Short intro",
                required=True,
                order=0,
                points=10,
                config={},
            )
            db.add(q)
            db.commit()

        assignment = db.query(Assignment).filter(Assignment.title == "E2E Test Assignment").first()
        if not assignment:
            assignment = Assignment(
                title="E2E Test Assignment",
                description="Assignment for candidate flow testing",
                form_id=form.id,
                start_date=datetime.now(timezone.utc),
                end_date=datetime.now(timezone.utc) + timedelta(days=30),
            )
            db.add(assignment)
            db.commit()
            db.refresh(assignment)

        candidate = (
            db.query(AssignmentUser)
            .filter(
                AssignmentUser.assignment_id == assignment.id,
                AssignmentUser.email == CANDIDATE_EMAIL,
            )
            .first()
        )
        if not candidate:
            candidate = AssignmentUser(
                assignment_id=assignment.id,
                email=CANDIDATE_EMAIL,
                deadline=datetime.now(timezone.utc) + timedelta(days=15),
                status="pending",
                token=secrets.token_urlsafe(32),
                email_sent=False,
            )
            db.add(candidate)
            db.commit()
            db.refresh(candidate)

        print("ADMIN_EMAIL=", ADMIN_EMAIL, sep="")
        print("ADMIN_PASSWORD=", ADMIN_PASSWORD, sep="")
        print("CANDIDATE_EMAIL=", CANDIDATE_EMAIL, sep="")
        print("CANDIDATE_EXAM_TOKEN=", candidate.token, sep="")
        print("ASSIGNMENT_ID=", assignment.id, sep="")
        print("DATABASE_URL_USED=", database_url, sep="")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
