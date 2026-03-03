"""
backend/models/mbg.py
Pydantic models untuk MBG weekly menus — Modul 6
"""
from typing import List, Optional

from pydantic import BaseModel


# ─── Response: satu hari dalam tampilan minggu ───

class WeeklyMenuEntry(BaseModel):
    date: str                        # "YYYY-MM-DD"
    day_name: str                    # "Senin", "Selasa", dst
    day_of_week: int                 # 1=Senin … 6=Sabtu
    menu_name: Optional[str] = None
    menu_id: Optional[str] = None
    has_bom: bool = False
    is_filled: bool = False
    notes: Optional[str] = None


# ─── Request: simpan/upsert menu satu hari ───

class WeeklyMenuCreate(BaseModel):
    date: str                        # "YYYY-MM-DD"
    menu_name: str
    menu_id: Optional[str] = None
    notes: Optional[str] = None


# ─── Request: update menu yang sudah ada ───

class WeeklyMenuUpdate(BaseModel):
    menu_name: str
    menu_id: Optional[str] = None
    notes: Optional[str] = None


# ─── Request: validasi nama menu + cek BOM ───

class ValidateMenuRequest(BaseModel):
    menu_name: str


# ─── Detail ingredient untuk response BOM ───

class BomIngredient(BaseModel):
    name: str
    qty: float
    unit: str


# ─── Response: hasil validasi menu + status BOM ───

class ValidateMenuResponse(BaseModel):
    found: bool
    product: Optional[dict] = None   # {id, name} atau null
    has_bom: bool = False
    bom_ingredients: List[BomIngredient] = []
