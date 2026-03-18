"""
Recipe / BOM management endpoints.
Includes component (reusable mini-recipe) CRUD.
"""

from decimal import Decimal
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from core.database import get_supabase
from core.dependencies import get_current_user, require_role
from models.recipe import (
    AttachComponentRequest,
    ComponentCreate,
    ComponentItemCreate,
    ComponentResponse,
    ComponentItemResponse,
    ComponentUpdate,
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
from services.recipe_service import recipe_service
from utils.unit_converter import get_base_unit, to_base

router = APIRouter(prefix="/recipes", tags=["recipes"])


# ═══════════════════════════════════════════════════════════════════════════════
# RECIPE CRUD (existing)
# ═══════════════════════════════════════════════════════════════════════════════

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
        "data": data,
        "total": len(data),
    }


@router.post("", response_model=Dict[str, Any], dependencies=[Depends(require_role(["owner", "admin"]))])
def create_recipe(
    body: RecipeCreate,
    current_user: UserInDB = Depends(get_current_user),
):
    """Create new recipe (direct ingredient)."""
    supabase = get_supabase()

    # Validasi menu category
    menu_resp = supabase.table("products").select("category").eq("id", body.menu_id).single().execute()
    menu_data = getattr(menu_resp, "data", None)
    if not menu_data or menu_data.get("category") != "produk_jadi":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Menu harus kategori produk_jadi",
        )

    # Validasi ingredient category
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

    # Convert qty from user-chosen unit to base unit
    _, input_factor = get_base_unit(body.unit)
    qty_in_base = float(body.qty_needed) * input_factor

    insert_data = {
        "tenant_id": current_user.tenant_id,
        "menu_id": body.menu_id,
        "ingredient_id": body.ingredient_id,
        "qty_needed": qty_in_base,
        "unit": body.unit,
        "usage_type": body.usage_type,
        "notes": body.notes,
    }

    # Handle per_hari daily_qty
    if body.usage_type == "per_hari" and body.daily_qty is not None:
        insert_data["daily_qty"] = float(body.daily_qty) * input_factor

    response = (
        supabase.table("recipes")
        .insert(insert_data)
        .execute()
    )

    data = getattr(response, "data", None) or []
    if not data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create recipe",
        )

    return {"success": True, "data": data[0]}


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
        if body.unit:
            _, input_factor = get_base_unit(body.unit)
            update_data["qty_needed"] = float(body.qty_needed) * input_factor
        else:
            update_data["qty_needed"] = float(body.qty_needed)
    if body.unit is not None:
        update_data["unit"] = body.unit
    if body.usage_type is not None:
        update_data["usage_type"] = body.usage_type
    if body.daily_qty is not None:
        if body.unit:
            _, input_factor = get_base_unit(body.unit)
            update_data["daily_qty"] = float(body.daily_qty) * input_factor
        else:
            update_data["daily_qty"] = float(body.daily_qty)
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

    return {"success": True, "data": data[0]}


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
    """Get recipe details for a menu (supports component expansion)."""
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

    # Flatten ingredients (expand components + direct)
    flat = {}  # {ingredient_id: total_qty}
    for recipe in recipes:
        if recipe.get("component_id"):
            # Expand component
            items_resp = (
                supabase.table("recipe_component_items")
                .select("ingredient_id, qty_needed")
                .eq("component_id", recipe["component_id"])
                .execute()
            )
            for item in (getattr(items_resp, "data", None) or []):
                ing_id = item["ingredient_id"]
                qty = Decimal(str(item["qty_needed"])) * Decimal(str(recipe.get("qty_needed", 1)))
                flat[ing_id] = flat.get(ing_id, Decimal("0")) + qty
        elif recipe.get("ingredient_id"):
            ing_id = recipe["ingredient_id"]
            qty = Decimal(str(recipe["qty_needed"]))
            flat[ing_id] = flat.get(ing_id, Decimal("0")) + qty

    # Build ingredient details with display values
    ingredients = []
    for ing_id, total_qty in flat.items():
        try:
            ing_resp = supabase.table("products").select("*").eq("id", ing_id).single().execute()
            ing_data = getattr(ing_resp, "data", None) or {}
        except Exception:
            ing_data = {}

        available = Decimal(str(ing_data.get("stock_qty", 0)))
        factor = float(ing_data.get("conversion_factor") or 1)
        disp_unit = ing_data.get("display_unit") or ing_data.get("unit", "")

        # Convert to display for showing to user
        qty_display = round(float(total_qty) / factor, 4) if factor else float(total_qty)
        avail_display = round(float(available) / factor, 4) if factor else float(available)

        ingredients.append(
            IngredientDetails(
                ingredient_id=ing_id,
                name=ing_data.get("name", "?"),
                unit=disp_unit,
                qty_needed=Decimal(str(qty_display)),
                current_stock=Decimal(str(avail_display)),
                is_sufficient=available >= total_qty,
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


@router.get("/simulate", response_model=Dict[str, Any])
def simulate_production(
    menu_id: str = Query(...),
    qty: int = Query(default=1),
    current_user: UserInDB = Depends(get_current_user),
):
    """Simulate production with component expansion."""
    supabase = get_supabase()

    result = recipe_service.calculate(
        menu_id=menu_id,
        qty=qty,
        tenant_id=current_user.tenant_id,
        supabase=supabase,
    )

    return {"success": True, "data": result}


# ═══════════════════════════════════════════════════════════════════════════════
# COMPONENT CRUD
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/components", response_model=Dict[str, Any])
def list_components(current_user: UserInDB = Depends(get_current_user)):
    """List all recipe components with their items."""
    supabase = get_supabase()

    resp = (
        supabase.table("recipe_components")
        .select("*")
        .eq("tenant_id", current_user.tenant_id)
        .order("name")
        .execute()
    )
    components = getattr(resp, "data", None) or []

    result = []
    for comp in components:
        # Get items for each component
        items_resp = (
            supabase.table("recipe_component_items")
            .select("*, products(name)")
            .eq("component_id", comp["id"])
            .execute()
        )
        items_data = getattr(items_resp, "data", None) or []

        items = []
        for item in items_data:
            product_info = item.get("products") or {}
            items.append(ComponentItemResponse(
                id=item["id"],
                component_id=item["component_id"],
                ingredient_id=item["ingredient_id"],
                qty_needed=Decimal(str(item["qty_needed"])),
                unit=item.get("unit"),
                product_name=product_info.get("name"),
            ))

        result.append(ComponentResponse(
            id=comp["id"],
            tenant_id=comp["tenant_id"],
            name=comp["name"],
            description=comp.get("description"),
            is_active=comp.get("is_active", True),
            created_at=comp.get("created_at"),
            items=items,
        ))

    return {"success": True, "data": result, "total": len(result)}


@router.post("/components", response_model=Dict[str, Any], dependencies=[Depends(require_role(["owner", "admin"]))])
def create_component(
    body: ComponentCreate,
    current_user: UserInDB = Depends(get_current_user),
):
    """Create new recipe component."""
    supabase = get_supabase()

    resp = (
        supabase.table("recipe_components")
        .insert({
            "tenant_id": current_user.tenant_id,
            "name": body.name,
            "description": body.description,
        })
        .execute()
    )
    data = getattr(resp, "data", None) or []
    if not data:
        raise HTTPException(status_code=500, detail="Gagal membuat komponen")

    return {"success": True, "data": ComponentResponse(**data[0], items=[])}


@router.put("/components/{component_id}", response_model=Dict[str, Any], dependencies=[Depends(require_role(["owner", "admin"]))])
def update_component(
    component_id: str,
    body: ComponentUpdate,
    current_user: UserInDB = Depends(get_current_user),
):
    """Update recipe component."""
    supabase = get_supabase()

    update_data = {}
    if body.name is not None:
        update_data["name"] = body.name
    if body.description is not None:
        update_data["description"] = body.description
    if body.is_active is not None:
        update_data["is_active"] = body.is_active

    if not update_data:
        raise HTTPException(status_code=400, detail="Tidak ada data untuk diupdate")

    resp = (
        supabase.table("recipe_components")
        .update(update_data)
        .eq("id", component_id)
        .eq("tenant_id", current_user.tenant_id)
        .execute()
    )
    data = getattr(resp, "data", None) or []
    if not data:
        raise HTTPException(status_code=404, detail="Komponen tidak ditemukan")

    return {"success": True, "data": data[0]}


@router.delete("/components/{component_id}", response_model=Dict[str, Any], dependencies=[Depends(require_role(["owner", "admin"]))])
def delete_component(
    component_id: str,
    current_user: UserInDB = Depends(get_current_user),
):
    """Delete component. Blocked if used by any menu."""
    supabase = get_supabase()

    # Check usage in recipes
    usage = (
        supabase.table("recipes")
        .select("id, menu_id")
        .eq("component_id", component_id)
        .eq("tenant_id", current_user.tenant_id)
        .execute()
    )
    used_by = getattr(usage, "data", None) or []
    if used_by:
        raise HTTPException(
            status_code=400,
            detail=f"Komponen dipakai oleh {len(used_by)} menu. Hapus dari menu dulu sebelum hapus komponen.",
        )

    supabase.table("recipe_components").delete().eq("id", component_id).eq("tenant_id", current_user.tenant_id).execute()

    return {"success": True, "message": "Komponen dihapus"}


@router.post("/components/{component_id}/items", response_model=Dict[str, Any], dependencies=[Depends(require_role(["owner", "admin"]))])
def add_component_item(
    component_id: str,
    body: ComponentItemCreate,
    current_user: UserInDB = Depends(get_current_user),
):
    """Add ingredient to component."""
    supabase = get_supabase()

    # Verify component belongs to tenant
    comp_resp = (
        supabase.table("recipe_components")
        .select("id")
        .eq("id", component_id)
        .eq("tenant_id", current_user.tenant_id)
        .execute()
    )
    if not (getattr(comp_resp, "data", None)):
        raise HTTPException(status_code=404, detail="Komponen tidak ditemukan")

    # Auto-fill unit from product if not provided
    unit = body.unit
    if not unit:
        prod_resp = supabase.table("products").select("unit, display_unit, conversion_factor").eq("id", body.ingredient_id).single().execute()
        prod_data = getattr(prod_resp, "data", None) or {}
        unit = prod_data.get("display_unit") or prod_data.get("unit", "kg")

    # Convert qty from input unit to base unit
    _, input_factor = get_base_unit(unit)
    qty_in_base = float(body.qty_needed) * input_factor

    insert_data = {
        "tenant_id": current_user.tenant_id,
        "component_id": component_id,
        "ingredient_id": body.ingredient_id,
        "qty_needed": qty_in_base,
        "unit": unit,
        "usage_type": body.usage_type,
    }
    if body.usage_type == "per_hari" and body.daily_qty is not None:
        insert_data["daily_qty"] = float(body.daily_qty) * input_factor

    resp = (
        supabase.table("recipe_component_items")
        .insert(insert_data)
        .execute()
    )
    data = getattr(resp, "data", None) or []
    if not data:
        raise HTTPException(status_code=500, detail="Gagal menambah bahan ke komponen")

    return {"success": True, "data": data[0]}


@router.delete("/components/{component_id}/items/{item_id}", response_model=Dict[str, Any], dependencies=[Depends(require_role(["owner", "admin"]))])
def delete_component_item(
    component_id: str,
    item_id: str,
    current_user: UserInDB = Depends(get_current_user),
):
    """Remove ingredient from component."""
    supabase = get_supabase()

    supabase.table("recipe_component_items").delete().eq("id", item_id).eq("component_id", component_id).execute()

    return {"success": True, "message": "Bahan dihapus dari komponen"}


# ═══════════════════════════════════════════════════════════════════════════════
# ATTACH COMPONENT TO MENU
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/attach-component", response_model=Dict[str, Any], dependencies=[Depends(require_role(["owner", "admin"]))])
def attach_component(
    body: AttachComponentRequest,
    current_user: UserInDB = Depends(get_current_user),
):
    """Attach a component to a menu recipe."""
    supabase = get_supabase()

    # Check duplicate
    existing = (
        supabase.table("recipes")
        .select("id")
        .eq("tenant_id", current_user.tenant_id)
        .eq("menu_id", body.menu_id)
        .eq("component_id", body.component_id)
        .execute()
    )
    if getattr(existing, "data", None):
        raise HTTPException(status_code=400, detail="Komponen sudah ditambahkan ke menu ini")

    resp = (
        supabase.table("recipes")
        .insert({
            "tenant_id": current_user.tenant_id,
            "menu_id": body.menu_id,
            "component_id": body.component_id,
            "ingredient_id": None,
            "qty_needed": 1,
            "unit": "komponen",
        })
        .execute()
    )
    data = getattr(resp, "data", None) or []
    if not data:
        raise HTTPException(status_code=500, detail="Gagal menambahkan komponen ke menu")

    return {"success": True, "data": data[0]}
