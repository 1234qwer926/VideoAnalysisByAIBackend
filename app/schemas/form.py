from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class QuestionCreate(BaseModel):
    type: str
    title: str
    description: Optional[str] = None
    required: bool = False
    order: int = 0
    points: int = 0
    config: dict = {}

class QuestionOut(QuestionCreate):
    id: int
    form_id: int

    class Config:
        from_attributes = True


class QuestionUpsert(BaseModel):
    id: Optional[int] = None
    type: str
    title: str
    prompt: Optional[str] = None
    required: bool = False
    order: int = 0
    points: int = 0
    options: List[str] = []
    section: Optional[str] = None
    section_time_seconds: Optional[int] = None


class FormCreate(BaseModel):
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    instructions: Optional[str] = None
    randomize_questions: bool = False
    questions: List[QuestionUpsert] = []


class FormUpdate(FormCreate):
    is_published: Optional[bool] = None


class FormOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    instructions: Optional[str]
    randomize_questions: bool
    is_published: bool
    created_at: datetime
    questions: List[QuestionOut] = []

    class Config:
        from_attributes = True
