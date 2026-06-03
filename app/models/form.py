from sqlalchemy import Column, Integer, String, Text, JSON, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base

class Form(Base):
    __tablename__ = "forms"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text)
    instructions = Column(Text)
    randomize_questions = Column(Boolean, default=False)
    is_published = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    questions = relationship("Question", back_populates="form", order_by="Question.order", cascade="all, delete-orphan")


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    form_id = Column(Integer, ForeignKey("forms.id", ondelete="CASCADE"))
    type = Column(String, nullable=False)
    # short_text | paragraph | mcq | checkbox | dropdown
    # file_upload | video | rating | yes_no | date | instruction
    title = Column(String, nullable=False)
    description = Column(Text)
    required = Column(Boolean, default=False)
    order = Column(Integer, default=0)
    points = Column(Integer, default=0)
    config = Column(JSON, default={})
    # config examples:
    # video   → { max_record_time: 120, min_record_time: 10, retry_allowed: true, face_detection: true }
    # mcq     → { options: ["A","B","C"], randomize: false }
    # rating  → { max: 5 }

    form = relationship("Form", back_populates="questions")