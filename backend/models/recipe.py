from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class RecipeCreate(BaseModel):
    menu_id: str
    ingredient_id: str
    qty_needed: Decimal
    unit: str
    notes: Optional[str] = None


class RecipeUpdate(BaseModel):
    qty_needed: Optional[Decimal] = None
    unit: Optional[str] = None
    notes: Optional[str] = None


class RecipeResponse(BaseModel):
    id: str
    tenant_id: str
    menu_id: str
    ingredient_id: str
    qty_needed: Decimal
    unit: str
    notes: Optional[str] = None
    created_at: str


class IngredientDetails(BaseModel):
    ingredient_id: str
    name: str
    unit: str
    qty_needed: Decimal
    current_stock: Decimal
    is_sufficient: bool


class MenuRecipeDetail(BaseModel):
    menu: dict  # {id, name, unit}
    ingredients: list[IngredientDetails]
    total_ingredients: int


class SimulateRequest(BaseModel):
    menu_id: str
    qty: int  # jumlah porsi yang akan diproduksi


class IngredientSimulation(BaseModel):
    name: str
    needed: Decimal
    available: Decimal
    sufficient: bool
    shortage: Decimal = Decimal("0.000")


class SimulateResponse(BaseModel):
    can_produce: bool
    max_possible: int
    ingredients: list[IngredientSimulation]
