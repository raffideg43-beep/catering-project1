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

    # ─── Helper methods ───

    def is_owner(self) -> bool:
        """Return True jika user adalah owner."""
        return self.role == "owner"

    def is_admin_or_above(self) -> bool:
        """Return True jika user adalah owner atau admin."""
        return self.role in ["owner", "admin"]

    def can_input(self) -> bool:
        """Return True jika user bisa input transaksi (owner, admin, kasir)."""
        return self.role in ["owner", "admin", "kasir"]

    def can_view_reports(self) -> bool:
        """Return True jika user bisa lihat laporan (owner, admin, viewer)."""
        return self.role in ["owner", "admin", "viewer"]


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





