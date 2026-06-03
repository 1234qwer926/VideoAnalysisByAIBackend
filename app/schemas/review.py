from pydantic import BaseModel
from typing import Optional

class ReviewUpdate(BaseModel):
    ai_score: Optional[float] = None
    admin_score: Optional[float] = None
    final_score: Optional[float] = None
    comments: Optional[str] = None
    question_scores: Optional[dict[int, float]] = None

class ReviewOut(ReviewUpdate):
    id: int
    submission_id: int

    class Config:
        from_attributes = True