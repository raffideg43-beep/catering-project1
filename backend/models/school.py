from typing import Optional

from pydantic import BaseModel


class SchoolCreate(BaseModel):
    name: str
    address: Optional[str] = None
    contact_name: Optional[str] = None
    default_portions: int = 0
    jumlah_siswa_l: int = 0
    jumlah_siswa_p: int = 0
    jumlah_pendidik: int = 0
    notes: Optional[str] = None


class SchoolUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    contact_name: Optional[str] = None
    default_portions: Optional[int] = None
    jumlah_siswa_l: Optional[int] = None
    jumlah_siswa_p: Optional[int] = None
    jumlah_pendidik: Optional[int] = None
    notes: Optional[str] = None


class SchoolResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    address: Optional[str] = None
    contact_name: Optional[str] = None
    default_portions: int = 0
    jumlah_siswa_l: int = 0
    jumlah_siswa_p: int = 0
    jumlah_pendidik: int = 0
    is_active: bool = True
    notes: Optional[str] = None
    created_at: str
