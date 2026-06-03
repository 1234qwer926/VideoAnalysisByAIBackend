from pydantic import BaseModel, EmailStr

class CandidateLogin(BaseModel):
    email: EmailStr
    password: str | None = None

class CandidateToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str = "candidate"
