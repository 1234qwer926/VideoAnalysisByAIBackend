from pydantic import BaseModel
from typing import Optional, Any, List
from datetime import datetime

class WarningCreate(BaseModel):
    type: str  # no_face | multiple_faces | looking_away

class WarningOut(BaseModel):
    id: int
    type: str
    timestamp: datetime

    class Config:
        from_attributes = True

class QuestionResponseCreate(BaseModel):
    question_id: int
    s3_key: Optional[str] = None
    answer: Optional[Any] = None

class SubmissionCreate(BaseModel):
    assignment_user_token: str
    responses: List[QuestionResponseCreate]
    is_auto_submitted: bool = False

class SubmissionOut(BaseModel):
    id: int
    assignment_user_id: int
    submitted_at: datetime
    is_auto_submitted: bool

    class Config:
        from_attributes = True