import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.models.submission import Submission, QuestionResponse

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

print("Submissions:")
for s in db.query(Submission).filter(Submission.id == 13).all():
    print(f"Sub ID: {s.id}, User ID: {s.assignment_user_id}")
    responses = db.query(QuestionResponse).filter(QuestionResponse.submission_id == s.id).all()
    print(f"  Responses count: {len(responses)}")
    for r in responses:
        print(f"    Q ID: {r.question_id}, s3_key: {r.s3_key}, ans: {r.answer}")
