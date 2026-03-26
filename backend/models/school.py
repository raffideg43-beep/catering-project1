from typing import Optional

from pydantic import BaseModel


class SchoolCreate(BaseModel):
    name: str
    address: Optional[str] = None
    contact_name: Optional[str] = None
    default_portions: int = 0
    notes: Optional[str] = None
    mbg_allocation_type: Optional[str] = "large"


class SchoolUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    contact_name: Optional[str] = None
    default_portions: Optional[int] = None
    notes: Optional[str] = None
    mbg_allocation_type: Optional[str] = None


class SchoolResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    address: Optional[str] = None
    contact_name: Optional[str] = None
    default_portions: int
    is_active: bool
    notes: Optional[str] = None
    mbg_allocation_type: Optional[str] = None
    created_at: str
