import logging
import json
import re
from typing import Optional, Dict, Any, Tuple
import httpx
from core.config import settings

logger = logging.getLogger(__name__)

# Prompt AI untuk Menebak Gizi dan Konversi Gram (Bila satuan nyeleneh)
NUTRITION_PROMPT = """Berikan estimasi tabel gizi dan berat bahan makanan berikut yang akan digunakan dalam dapur katering.
Nama Bahan: {material_name}
Satuan Kasar: {satuan}

Return WAJIB JSON murni tanpa markdown:
{{
  "name": "Nama Makanan Baku (Contoh: Bawang Merah, Daging Sapi, dsb)",
  "kategori": "sayur" | "lauk hewani" | "lauk nabati" | "karbohidrat" | "buah" | "bumbu" | "lainnya",
  "calories_per_100g": 0.0,
  "proteins_per_100g": 0.0,
  "fat_per_100g": 0.0,
  "carbohydrate_per_100g": 0.0,
  "estimated_gram_per_unit": 100.0,
  "reasoning": "Sebutkan darimana asumsi berat 1 {satuan} {material_name} berasal secara singkat."
}}

ATURAN WAJIB:
- Jika satuan adalah "siung", "ikat", "lembar", "pack", "buah", "biji", perkirakan berat rata-ratanya di Indonesia pada 'estimated_gram_per_unit'.
- Jika satuan adalah "pcs/buah/ekor", perkirakan. Jika "kg/liter", isi estimated_gram_per_unit = 1000.
"""

class NutritionService:
    def __init__(self):
        self.api_key = settings.gemini_api_key
        self.model = settings.gemini_ocr_model  # Pakai flash untuk kehematan as general text
        self.api_url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )

    def guess_and_create_nutrition(self, supabase, material_name: str, satuan: str) -> Optional[Dict[str, Any]]:
        """
        Hit Gemini AI and returns dict with nutrition and gram conversion.
        Insert it to nutrition_ref if successful.
        """
        if not self.api_key:
            logger.error("GEMINI_API_KEY tidak dikonfigurasi")
            return None

        prompt = NUTRITION_PROMPT.format(material_name=material_name, satuan=satuan)

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 1024,
            },
        }

        try:
            with httpx.Client(timeout=30) as client:
                resp = client.post(self.api_url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            text = re.sub(r"```json\s*", "", text)
            text = re.sub(r"```\s*", "", text)
            ai_data = json.loads(text.strip())
            
            # Insert ke nutrition_ref
            insert_resp = supabase.table("nutrition_ref").insert({
                "name": ai_data.get("name", material_name),
                "calories": float(ai_data.get("calories_per_100g", 0)),
                "proteins": float(ai_data.get("proteins_per_100g", 0)),
                "fat": float(ai_data.get("fat_per_100g", 0)),
                "carbohydrate": float(ai_data.get("carbohydrate_per_100g", 0)),
                "kategori": ai_data.get("kategori", "lainnya")
            }).execute()
            
            inserted = getattr(insert_resp, "data", [])
            if inserted:
                ai_data["nutrition_ref_id"] = inserted[0]["id"]
                return ai_data
                
            return None
            
        except Exception as e:
            logger.error(f"Gemini AI Nutrition Error / Parse: {e}")
            return None

    def map_and_link_product(self, supabase, product_id: str, product_name: str, satuan: str, tenant_id: str):
        """
        Fuzzy search nutrition_ref, if not found hit AI, then alter products.nutrition_ref_id
        And if AI found a valid estimated_gram_per_unit, update products.conversion_factor too!
        """
        # Trigram matching (Butuh extension pg_trgm yang aktif di db)
        query = supabase.rpc("match_nutrition_trgm", {"search_term": product_name}).execute()
        matches = getattr(query, "data", [])
        
        nutrition_id = None
        conversion_to_update = None
        
        if matches and float(matches[0].get("similarity", 0)) > 0.4:
            nutrition_id = matches[0]["id"]
        else:
            # Panggil Gemini!
            ai_res = self.guess_and_create_nutrition(supabase, product_name, satuan)
            if ai_res:
                nutrition_id = ai_res.get("nutrition_ref_id")
                # Kita ubah conversion_factor
                conversion_to_update = ai_res.get("estimated_gram_per_unit")

        # Update table products dengan foreign key baru dan atau conversion factor
        if nutrition_id:
            update_payload = {"nutrition_ref_id": nutrition_id}
            if conversion_to_update and float(conversion_to_update) > 0:
                 update_payload["conversion_factor"] = float(conversion_to_update)
            
            supabase.table("products").update(update_payload).eq("id", product_id).eq("tenant_id", tenant_id).execute()
        
        return nutrition_id

nutrition_svc = NutritionService()
