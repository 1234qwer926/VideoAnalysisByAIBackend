from pydantic import BaseModel, EmailStr

class AdminLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str = "admin"

class AdminOut(BaseModel):
    id: int
    email: str

    class Config:
        from_attributes = True