"""
Recipe / BOM management endpoints.
"""

from decimal import Decimal
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status

from core.database import get_supabase
from core.dependencies import get_current_user, require_role
from models.recipe import (
    IngredientDetails,
    MenuRecipeDetail,
    RecipeCreate,
    RecipeResponse,
    RecipeUpdate,
    SimulateRequest,
    SimulateResponse,
    IngredientSimulation,
)
from models.user import UserInDB

router = APIRouter(prefix="/recipes", tags=["recipes"])


@router.get("", response_model=Dict[str, Any])
def list_recipes(current_user: UserInDB = Depends(get_current_user)):
    """List all recipes."""
    supabase = get_supabase()

    response = (
        supabase.table("recipes")
        .select("*")
        .eq("tenant_id", current_user.tenant_id)
        .execute()
    )

    data = getattr(response, "data", None) or []

    return {
        "success": True,
        "data": [RecipeResponse(**r) for r in data],
        "total": len(data),
    }


@router.post("", response_model=Dict[str, Any], dependencies=[Depends(require_role(["owner", "admin"]))])
def create_recipe(
    body: RecipeCreate,
    current_user: UserInDB = Depends(get_current_user),
):
    """Create new recipe."""
    supabase = get_supabase()

    # Validasi menu dan ingredient category
    menu_resp = supabase.table("products").select("category").eq("id", body.menu_id).single().execute()
    menu_data = getattr(menu_resp, "data", None)
    if not menu_data or menu_data.get("category") != "produk_jadi":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Menu harus kategori produk_jadi",
        )

    ingredient_resp = (
        supabase.table("products").select("category").eq("id", body.ingredient_id).single().execute()
    )
    ingredient_data = getattr(ingredient_resp, "data", None)
    if not ingredient_data or ingredient_data.get("category") != "bahan_baku":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bahan harus kategori bahan_baku",
        )

    # Cek duplikat
    existing = (
        supabase.table("recipes")
        .select("id")
        .eq("tenant_id", current_user.tenant_id)
        .eq("menu_id", body.menu_id)
        .eq("ingredient_id", body.ingredient_id)
        .execute()
    )
    if getattr(existing, "data", None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resep ini sudah ada",
        )

    response = (
        supabase.table("recipes")
        .insert(
            {
                "tenant_id": current_user.tenant_id,
                "menu_id": body.menu_id,
                "ingredient_id": body.ingredient_id,
                "qty_needed": float(body.qty_needed),
                "unit": body.unit,
                "notes": body.notes,
            }
        )
        .execute()
    )

    data = getattr(response, "data", None) or []
    if not data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create recipe",
        )

    return {"success": True, "data": RecipeResponse(**data[0])}


@router.put("/{recipe_id}", response_model=Dict[str, Any], dependencies=[Depends(require_role(["owner", "admin"]))])
def update_recipe(
    recipe_id: str,
    body: RecipeUpdate,
    current_user: UserInDB = Depends(get_current_user),
):
    """Update recipe."""
    supabase = get_supabase()

    update_data = {}
    if body.qty_needed is not None:
        update_data["qty_needed"] = float(body.qty_needed)
    if body.unit is not None:
        update_data["unit"] = body.unit
    if body.notes is not None:
        update_data["notes"] = body.notes

    response = (
        supabase.table("recipes")
        .update(update_data)
        .eq("id", recipe_id)
        .eq("tenant_id", current_user.tenant_id)
        .execute()
    )

    data = getattr(response, "data", None) or []
    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found")

    return {"success": True, "data": RecipeResponse(**data[0])}


@router.delete("/{recipe_id}", response_model=Dict[str, Any], dependencies=[Depends(require_role(["owner", "admin"]))])
def delete_recipe(
    recipe_id: str,
    current_user: UserInDB = Depends(get_current_user),
):
    """Delete recipe (hard delete)."""
    supabase = get_supabase()

    supabase.table("recipes").delete().eq("id", recipe_id).eq("tenant_id", current_user.tenant_id).execute()

    return {"success": True, "message": "Recipe deleted"}


@router.get("/menu/{menu_id}", response_model=Dict[str, Any])
def get_menu_recipe(
    menu_id: str,
    current_user: UserInDB = Depends(get_current_user),
):
    """Get recipe details untuk menu."""
    supabase = get_supabase()

    # Get menu
    menu_resp = (
        supabase.table("products")
        .select("id, name, unit")
        .eq("id", menu_id)
        .eq("tenant_id", current_user.tenant_id)
        .single()
        .execute()
    )
    menu_data = getattr(menu_resp, "data", None)
    if not menu_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu not found")

    # Get recipes
    resp = (
        supabase.table("recipes")
        .select("*")
        .eq("menu_id", menu_id)
        .eq("tenant_id", current_user.tenant_id)
        .execute()
    )
    recipes = getattr(resp, "data", None) or []

    # Build ingredient list dengan stok
    ingredients = []
    for recipe in recipes:
        ingredient_id = recipe["ingredient_id"]
        ing_resp = supabase.table("products").select("*").eq("id", ingredient_id).single().execute()
        ing_data = getattr(ing_resp, "data", None) or {}

        ingredients.append(
            IngredientDetails(
                ingredient_id=ingredient_id,
                name=ing_data.get("name", ""),
                unit=ing_data.get("unit", ""),
                qty_needed=Decimal(str(recipe["qty_needed"])),
                current_stock=Decimal(str(ing_data.get("stock_qty", 0))),
                is_sufficient=Decimal(str(ing_data.get("stock_qty", 0))) >= Decimal(str(recipe["qty_needed"])),
            )
        )

    return {
        "success": True,
        "data": MenuRecipeDetail(
            menu=menu_data,
            ingredients=ingredients,
            total_ingredients=len(ingredients),
        ),
    }


@router.post("/simulate", response_model=Dict[str, Any])
def simulate_production(
    body: SimulateRequest,
    current_user: UserInDB = Depends(get_current_user),
):
    """Simulate production untuk menu tertentu."""
    supabase = get_supabase()

    # Get recipes untuk menu
    resp = (
        supabase.table("recipes")
        .select("*")
        .eq("menu_id", body.menu_id)
        .eq("tenant_id", current_user.tenant_id)
        .execute()
    )
    recipes = getattr(resp, "data", None) or []

    if not recipes:
        return {
            "success": True,
            "data": SimulateResponse(
                can_produce=True,
                max_possible=body.qty,
                ingredients=[],
            ),
        }

    ingredients_sim = []
    min_batches = float("inf")

    for recipe in recipes:
        ingredient_id = recipe["ingredient_id"]
        ing_resp = supabase.table("products").select("*").eq("id", ingredient_id).single().execute()
        ing_data = getattr(ing_resp, "data", None) or {}

        needed = Decimal(str(recipe["qty_needed"])) * body.qty
        available = Decimal(str(ing_data.get("stock_qty", 0)))
        sufficient = available >= needed
        shortage = Decimal("0") if sufficient else needed - available

        # Hitung max batch untuk bahan ini
        if recipe["qty_needed"] > 0:
            max_batch = int(float(available) / float(recipe["qty_needed"]))
            min_batches = min(min_batches, max_batch)

        ingredients_sim.append(
            IngredientSimulation(
                name=ing_data.get("name", ""),
                needed=needed,
                available=available,
                sufficient=sufficient,
                shortage=shortage,
            )
        )

    can_produce = all(ing.sufficient for ing in ingredients_sim)
    max_possible = int(min_batches) if min_batches != float("inf") else body.qty

    return {
        "success": True,
        "data": SimulateResponse(
            can_produce=can_produce,
            max_possible=max_possible,
            ingredients=ingredients_sim,
        ),
    }
