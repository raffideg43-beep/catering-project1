from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from pydantic.fields import Field

from core.database import get_supabase
from core.dependencies import get_current_user
from models.user import UserInDB

router = APIRouter(prefix="/nutrition", tags=["nutrition"])

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
    
    # 1. Ambil resep/BOM dari menu ini
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
        Usage_Type = r.get("usage_type", "per_porsi")
        if Usage_Type != "per_porsi":
            continue
            
        qty = float(r.get("qty_needed", 0))
        prod = r.get("products")
        if not prod:
            continue
            
        conv_factor = float(prod.get("conversion_factor") or 1.0)
        weight_in_gram = qty * conv_factor
        
        # Now fetch the nutrition ref
        nut_id = prod.get("nutrition_ref_id")
        if not nut_id:
            continue
            
        nut_resp = supabase.table("nutrition_ref").select("*").eq("id", nut_id).single().execute()
        nref = getattr(nut_resp, "data", None)
        if not nref:
            continue
            
        kategori = nref.get("kategori", "").lower()
        
        # nutrition_ref stores values per 100g.
        multiplier = weight_in_gram / 100.0
        
        total_cal += float(nref.get("calories", 0)) * multiplier
        total_protein += float(nref.get("proteins", 0)) * multiplier
        total_fat += float(nref.get("fat", 0)) * multiplier
        total_carbs += float(nref.get("carbohydrate", 0)) * multiplier
        
        total_gram += weight_in_gram
        if "sayur" in kategori:
            sayur_gram += weight_in_gram

    perc = 0.0
    if total_gram > 0:
        perc = (sayur_gram / total_gram) * 100.0
        
    return NutritionSummary(
        menu_id=menu_id,
        calories=round(total_cal, 1),
        proteins=round(total_protein, 1),
        fat=round(total_fat, 1),
        carbohydrates=round(total_carbs, 1),
        total_ingredient_gram=round(total_gram, 1),
        sayur_percentage=round(perc, 1),
        is_balanced=perc >= 30.0
    )


# ─── NEW: Detail per-bahan endpoint ────────────────────────────────────────────

@router.get("/menu/{menu_id}/details")
async def get_menu_nutrition_details(
    menu_id: str,
    active_user: UserInDB = Depends(get_current_user)
):
    """
    Return nutrisi per-bahan (per ingredient) untuk 1 porsi menu.
    Digunakan oleh tabel nutrisi detail di frontend BOM.
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
        conv_factor = float(prod.get("conversion_factor") or 1.0)
        qty = float(r.get("qty_needed", 0))
        weight_gram = qty * conv_factor
        
        nut_id = prod.get("nutrition_ref_id")
        cal = 0.0
        prot = 0.0
        fat = 0.0
        carb = 0.0
        kategori = ""
        nut_name = ""
        
        if nut_id:
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
    
    # 1. Update di tabel products (e.g. conversion_factor 1 siung = 5 gr)
    if req.conversion_factor is not None:
        supabase.table("products").update({"conversion_factor": req.conversion_factor}).eq("id", product_id).eq("tenant_id", active_user.tenant_id).execute()
        
    # 2. Ambil nutrition_ref_id
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


# ─── Auto-link endpoint (trigger dari frontend) ────────────────────────────────

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
