from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

class AssignmentCreate(BaseModel):
    title: str
    description: Optional[str] = None
    form_id: int
    knowledge_base: Optional[str] = None
    ai_prompt: Optional[str] = None
    overall_timer_minutes: Optional[int] = None
    per_question_timer_seconds: Optional[int] = None
    submission_timer_minutes: Optional[int] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

class AssignmentOut(AssignmentCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class AssignmentUserCreate(BaseModel):
    email: EmailStr
    deadline: Optional[datetime] = None

class AssignmentUserBulk(BaseModel):
    entries: List[AssignmentUserCreate]

class AssignmentUserOut(BaseModel):
    id: int
    email: str
    deadline: Optional[datetime] = None
    status: str
    token: str
    email_sent: bool

    class Config:
        from_attributes = True
