from typing import Optional

from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: str = "owner"
    telegram_id: Optional[int] = None


class UserInDB(BaseModel):
    id: str
    tenant_id: str
    telegram_id: Optional[int] = None
    email: EmailStr
    name: str
    role: str
    is_active: bool = True

    class Config:
        extra = "ignore"


class UserResponse(BaseModel):
    id: str
    name: str
    email: EmailStr
    role: str
    tenant_id: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


