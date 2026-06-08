from pydantic import BaseModel, EmailStr, field_validator

class AdminLogin(BaseModel):
    """Schema for login endpoint — accepts any password (verification happens against stored hash)."""
    email: EmailStr
    password: str


class AdminRegister(BaseModel):
    """Schema for registration — enforces strong password policy."""
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 12:
            raise ValueError("Password must be at least 12 characters")
        return v

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str = "admin"

class AdminOut(BaseModel):
    id: int
    email: str

    class Config:
        from_attributes = True

class GoogleAuthRequest(BaseModel):
    token: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_must_be_strong(cls, v: str) -> str:
        if len(v) < 12:
            raise ValueError("Password must be at least 12 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in v):
            raise ValueError("Password must contain at least one special character")
        return v