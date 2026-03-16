from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class ProductCreate(BaseModel):
    name: str
    sku: Optional[str] = None
    category: str
    unit: str = "pcs"
    hpp: Decimal = Decimal("0.00")
    sell_price: Decimal = Decimal("0.00")
    stock_qty: Decimal = Decimal("0.000")
    stock_min: Decimal = Decimal("0.000")
    notes: Optional[str] = None


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    sku: Optional[str] = None
    category: Optional[str] = None
    unit: Optional[str] = None
    hpp: Optional[Decimal] = None
    sell_price: Optional[Decimal] = None
    stock_min: Optional[Decimal] = None
    notes: Optional[str] = None


class ProductResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    sku: Optional[str] = None
    category: str
    unit: str
    hpp: Decimal
    sell_price: Decimal
    stock_qty: Decimal
    stock_min: Decimal
    is_active: bool
    notes: Optional[str] = None
    created_at: str


class StockAdjustRequest(BaseModel):
    change_qty: Decimal
    reason: str  # adjustment, spoilage, waste
    notes: Optional[str] = None


class StockManualAdjustRequest(BaseModel):
    """Koreksi stok manual — menerima stok fisik baru, bukan delta."""
    new_qty: Decimal
    reason: str  # deskripsi singkat alasan koreksi
    notes: Optional[str] = None
