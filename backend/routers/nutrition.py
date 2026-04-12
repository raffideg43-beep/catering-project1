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

    # Note: Kita bisa menjumlahkan seluruh `qty_needed` di BOM per porsi
    # pastikan "usage_type" = "per_porsi" jika ingin tepat 1 porsi.
    # Jika "per_hari", kita abaikan saja karena bukan hitungan bahan ke perut (kecuali itu beras/gas, tapi biasanya per_porsi).
    
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
        # Assuming conversion factor converts usage unit (like butir/siung/kg) to baseline Gram
        
        # e.g., if usage unit is kg, conversion_factor=1000. So 0.05 kg * 1000 = 50 g
        # e.g., if usage unit is butir (egg), conversion_factor=60. So 1 butir * 60 = 60 g
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


# --- Endpoint Edit Manual Konversi (Sesuai Permintaan User) ---
class NutritionEditRequest(BaseModel):
    product_id: str
    conversion_factor: Optional[float] = None
    calories: Optional[float] = None
    proteins: Optional[float] = None
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
        if req.kategori is not None: update_nut["kategori"] = req.kategori
        if update_nut:
            supabase.table("nutrition_ref").update(update_nut).eq("id", nut_id).execute()
            
    return {"success": True, "message": "Berhasil memperbarui rujukan gizi produk."}
