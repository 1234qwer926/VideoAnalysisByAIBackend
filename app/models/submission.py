from sqlalchemy import Column, Integer, String, JSON, DateTime, Boolean, ForeignKey, Float
from sqlalchemy.sql import func
from app.db.database import Base

class Submission(Base):
    __tablename__ = "submissions"

    id = Column(Integer, primary_key=True, index=True)
    assignment_user_id = Column(Integer, ForeignKey("assignment_users.id"))
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())
    is_auto_submitted = Column(Boolean, default=False)


class QuestionResponse(Base):
    __tablename__ = "question_responses"

    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey("submissions.id", ondelete="CASCADE"))
    question_id = Column(Integer, ForeignKey("questions.id"))
    s3_key = Column(String)          # for video answers
    answer = Column(JSON)            # for text/mcq/etc answers
    upload_time = Column(DateTime(timezone=True))
    score = Column(Float, nullable=True)


class WarningLog(Base):
    __tablename__ = "warning_logs"

    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey("submissions.id", ondelete="CASCADE"))
    type = Column(String)            # no_face | multiple_faces | looking_away
    timestamp = Column(DateTime(timezone=True), server_default=func.now())