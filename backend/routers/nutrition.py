from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from pydantic.fields import Field

from core.database import get_supabase
from core.dependencies import get_current_user
from models.user import UserInDB

router = APIRouter(prefix="/nutrition", tags=["nutrition"])


def _recipe_to_grams(r: dict, prod: dict) -> float:
    """
    Convert recipe qty_needed to grams properly.
    
    Recipe stores qty_needed in the unit specified in recipe.unit (e.g. 'gram', 'kg', 'pcs').
    Product has conversion_factor which converts product.unit to grams.
    
    Rules:
    - If recipe.unit is 'gram' or 'g' → qty_needed IS grams already
    - If recipe.unit is 'kg' → qty_needed * 1000
    - If recipe.unit is 'liter' or 'ml' → qty_needed * 1000 or 1
    - If recipe.unit matches product.unit → qty_needed * product.conversion_factor
    - Otherwise use qty_needed as-is (best effort)
    """
    qty = float(r.get("qty_needed", 0))
    recipe_unit = (r.get("unit") or "").lower().strip()
    
    # Direct gram/g
    if recipe_unit in ("gram", "g", "gr"):
        return qty
    
    # kg
    if recipe_unit == "kg":
        return qty * 1000
    
    # liter
    if recipe_unit == "liter" or recipe_unit == "l":
        return qty * 1000  # approximation: 1L ≈ 1000g for water/oil
    
    # ml
    if recipe_unit in ("ml", "mililiter"):
        return qty
    
    # pcs/buah/butir/siung etc — use product's conversion_factor 
    # (which represents grams per 1 unit of the product's display unit)
    prod_conv = float(prod.get("conversion_factor") or 1.0)
    prod_unit = (prod.get("unit") or "").lower().strip()
    
    # If product unit matches recipe unit, use conversion_factor
    if recipe_unit == prod_unit.lower():
        return qty * prod_conv
    
    # Fallback for pcs/buah/butir etc
    if recipe_unit in ("pcs", "buah", "butir", "siung", "lembar", "ikat", "biji", "ekor", "batang"):
        # conversion_factor for pcs-based products typically = grams per 1 piece
        return qty * prod_conv
    
    # Ultimate fallback: assume it's already grams
    return qty


class NutritionSummary(BaseModel):
    menu_id: str
    calories: float = 0.0
    proteins: float = 0.0
    fat: float = 0.0
    carbohydrates: float = 0.0
    total_ingredient_gram: float = 0.0
    sayur_percentage: float = 0.0
    is_balanced: bool = True


@router.get("/menu/{menu_id}", response_model=NutritionSummary)
async def get_menu_nutrition_summary(
    menu_id: str,
    active_user: UserInDB = Depends(get_current_user)
):
    """
    Hitung nilai standimetri gizi per porsi pada Menu BOM.
    """
    supabase = get_supabase()
    
    recipes_resp = supabase.table("recipes").select("*, products!recipes_ingredient_id_fkey(*)").eq("menu_id", menu_id).execute()
    recipes = getattr(recipes_resp, "data", [])
    
    if not recipes:
        return NutritionSummary(menu_id=menu_id)

    total_cal = 0.0
    total_protein = 0.0
    total_fat = 0.0
    total_carbs = 0.0
    total_gram = 0.0
    sayur_gram = 0.0
    
    for r in recipes:
        if r.get("usage_type", "per_porsi") != "per_porsi":
            continue
            
        prod = r.get("products")
        if not prod:
            continue
        
        weight_in_gram = _recipe_to_grams(r, prod)
        if weight_in_gram <= 0:
            continue
        
        nut_id = prod.get("nutrition_ref_id")
        if not nut_id:
            total_gram += weight_in_gram
            continue
            
        try:
            nut_resp = supabase.table("nutrition_ref").select("*").eq("id", nut_id).single().execute()
            nref = getattr(nut_resp, "data", None)
        except Exception:
            nref = None
            
        if not nref:
            total_gram += weight_in_gram
            continue
            
        kategori = nref.get("kategori", "").lower()
        multiplier = weight_in_gram / 100.0
        
        total_cal += float(nref.get("calories", 0)) * multiplier
        total_protein += float(nref.get("proteins", 0)) * multiplier
        total_fat += float(nref.get("fat", 0)) * multiplier
        total_carbs += float(nref.get("carbohydrate", 0)) * multiplier
        
        total_gram += weight_in_gram
        if "sayur" in kategori:
            sayur_gram += weight_in_gram

    perc = round((sayur_gram / total_gram) * 100.0, 1) if total_gram > 0 else 0.0
        
    return NutritionSummary(
        menu_id=menu_id,
        calories=round(total_cal, 1),
        proteins=round(total_protein, 1),
        fat=round(total_fat, 1),
        carbohydrates=round(total_carbs, 1),
        total_ingredient_gram=round(total_gram, 1),
        sayur_percentage=perc,
        is_balanced=perc >= 30.0
    )


# ─── Detail per-bahan endpoint ─────────────────────────────────────────────────

@router.get("/menu/{menu_id}/details")
async def get_menu_nutrition_details(
    menu_id: str,
    active_user: UserInDB = Depends(get_current_user)
):
    """
    Return nutrisi per-bahan (per ingredient) untuk 1 porsi menu.
    """
    supabase = get_supabase()
    
    recipes_resp = (
        supabase.table("recipes")
        .select("*, products!recipes_ingredient_id_fkey(id, name, unit, display_unit, conversion_factor, nutrition_ref_id)")
        .eq("menu_id", menu_id)
        .execute()
    )
    recipes = getattr(recipes_resp, "data", [])
    
    ingredients = []
    total_cal = 0.0
    total_prot = 0.0
    total_fat = 0.0
    total_carb = 0.0
    total_gram = 0.0
    sayur_gram = 0.0
    
    for r in recipes:
        if r.get("usage_type", "per_porsi") != "per_porsi":
            continue
        
        prod = r.get("products")
        if not prod:
            continue
        
        product_id = prod.get("id", "")
        product_name = prod.get("name", "?")
        weight_gram = _recipe_to_grams(r, prod)
        
        nut_id = prod.get("nutrition_ref_id")
        cal = 0.0
        prot = 0.0
        fat = 0.0
        carb = 0.0
        kategori = ""
        nut_name = ""
        
        if nut_id and weight_gram > 0:
            try:
                nut_resp = supabase.table("nutrition_ref").select("*").eq("id", nut_id).single().execute()
                nref = getattr(nut_resp, "data", None)
                if nref:
                    multiplier = weight_gram / 100.0
                    cal = round(float(nref.get("calories", 0)) * multiplier, 1)
                    prot = round(float(nref.get("proteins", 0)) * multiplier, 1)
                    fat = round(float(nref.get("fat", 0)) * multiplier, 1)
                    carb = round(float(nref.get("carbohydrate", 0)) * multiplier, 1)
                    kategori = nref.get("kategori", "")
                    nut_name = nref.get("name", "")
            except Exception:
                pass
        
        total_cal += cal
        total_prot += prot
        total_fat += fat
        total_carb += carb
        total_gram += weight_gram
        if "sayur" in kategori.lower():
            sayur_gram += weight_gram
        
        ingredients.append({
            "product_id": product_id,
            "product_name": product_name,
            "weight_gram": round(weight_gram, 1),
            "calories": cal,
            "proteins": prot,
            "fat": fat,
            "carbohydrate": carb,
            "kategori": kategori,
            "nutrition_ref_id": nut_id,
            "nutrition_ref_name": nut_name,
            "has_nutrition": nut_id is not None,
        })
    
    sayur_pct = round((sayur_gram / total_gram) * 100, 1) if total_gram > 0 else 0.0
    
    return {
        "success": True,
        "data": {
            "menu_id": menu_id,
            "ingredients": ingredients,
            "totals": {
                "calories": round(total_cal, 1),
                "proteins": round(total_prot, 1),
                "fat": round(total_fat, 1),
                "carbohydrate": round(total_carb, 1),
                "total_gram": round(total_gram, 1),
            },
            "sayur_percentage": sayur_pct,
            "is_balanced": sayur_pct >= 30.0,
        }
    }


# ─── Edit Manual Konversi & Gizi ────────────────────────────────────────────────

class NutritionEditRequest(BaseModel):
    product_id: str
    conversion_factor: Optional[float] = None
    calories: Optional[float] = None
    proteins: Optional[float] = None
    fat: Optional[float] = None
    carbohydrate: Optional[float] = None
    kategori: Optional[str] = None
    
@router.put("/products/{product_id}")
async def update_nutrition_estimation(
    product_id: str,
    req: NutritionEditRequest,
    active_user: UserInDB = Depends(get_current_user)
):
    """
    Koreksi manual jika tebakan Gemini API melenceng.
    """
    supabase = get_supabase()
    
    if req.conversion_factor is not None:
        supabase.table("products").update({"conversion_factor": req.conversion_factor}).eq("id", product_id).eq("tenant_id", active_user.tenant_id).execute()
        
    p_resp = supabase.table("products").select("nutrition_ref_id").eq("id", product_id).single().execute()
    prod = getattr(p_resp, "data", {})
    nut_id = prod.get("nutrition_ref_id")
    
    if nut_id:
        update_nut = {}
        if req.calories is not None: update_nut["calories"] = req.calories
        if req.proteins is not None: update_nut["proteins"] = req.proteins
        if req.fat is not None: update_nut["fat"] = req.fat
        if req.carbohydrate is not None: update_nut["carbohydrate"] = req.carbohydrate
        if req.kategori is not None: update_nut["kategori"] = req.kategori
        if update_nut:
            supabase.table("nutrition_ref").update(update_nut).eq("id", nut_id).execute()
            
    return {"success": True, "message": "Berhasil memperbarui rujukan gizi produk."}


# ─── Auto-link endpoint ────────────────────────────────────────────────────────

@router.post("/auto-link/{product_id}")
async def auto_link_nutrition(
    product_id: str,
    active_user: UserInDB = Depends(get_current_user)
):
    """
    Auto-link satu produk ke nutrition_ref via fuzzy match atau AI.
    """
    supabase = get_supabase()
    
    p_resp = supabase.table("products").select("id, name, unit, nutrition_ref_id").eq("id", product_id).eq("tenant_id", active_user.tenant_id).single().execute()
    prod = getattr(p_resp, "data", None)
    if not prod:
        raise HTTPException(404, "Product not found")
    
    if prod.get("nutrition_ref_id"):
        return {"success": True, "message": "Sudah ter-link", "nutrition_ref_id": prod["nutrition_ref_id"]}
    
    from services.nutrition_service import nutrition_svc
    nut_id = nutrition_svc.map_and_link_product(
        supabase, product_id, prod["name"], prod.get("unit", "gram"), active_user.tenant_id
    )
    
    return {
        "success": True,
        "message": "Berhasil di-link" if nut_id else "Tidak ditemukan data nutrisi",
        "nutrition_ref_id": nut_id,
    }
