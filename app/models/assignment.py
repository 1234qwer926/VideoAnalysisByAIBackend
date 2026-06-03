from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base

class Assignment(Base):
    __tablename__ = "assignments"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text)
    form_id = Column(Integer, ForeignKey("forms.id"))
    knowledge_base = Column(Text)
    ai_prompt = Column(Text)
    overall_timer_minutes = Column(Integer)        # None = no timer
    per_question_timer_seconds = Column(Integer)   # None = no timer
    submission_timer_minutes = Column(Integer)
    start_date = Column(DateTime(timezone=True))
    end_date = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    users = relationship("AssignmentUser", back_populates="assignment", cascade="all, delete-orphan")


class AssignmentUser(Base):
    __tablename__ = "assignment_users"

    id = Column(Integer, primary_key=True, index=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id", ondelete="CASCADE"))
    email = Column(String, nullable=False, index=True)
    deadline = Column(DateTime(timezone=True))
    status = Column(String, default="pending")     # pending | started | completed | expired
    token = Column(String, unique=True, index=True)
    email_sent = Column(Boolean, default=False)

    assignment = relationship("Assignment", back_populates="users")