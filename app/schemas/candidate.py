from pydantic import BaseModel, EmailStr

class CandidateLogin(BaseModel):
    email: EmailStr
    password: str  # Required — None/optional passwords allow passwordless authentication

class CandidateToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str = "candidate"
    user: dict | None = None  # Include user info (name, email, picture)
