"""
backend/services/gram_converter.py
AI-powered "Timbangan Digital Virtual" — converts portion descriptions to grams using Gemini.

Usage:
  converter = GramConverterService()
  grams = await converter.convert("3 iris timun")   # → 15
  nutrition = await converter.calculate_nutrition("timun", "3 iris", tenant_id, supabase)
"""

import json
import logging
import re
from typing import Any, Dict, Optional

from core.config import settings

logger = logging.getLogger(__name__)

# ─── System Prompt (hemat token, akurat) ────────────────────────────────────
SYSTEM_INSTRUCTION = """Kamu adalah asisten ahli gizi katering Indonesia (MBG - Makan Bergizi Gratis).
Tugasmu HANYA mengonversi satuan porsi makanan menjadi berat dalam GRAM.
Gunakan standar rata-rata porsi katering sekolah Indonesia.

ATURAN KETAT:
1. Balas HANYA dengan angka integer (gram), TANPA teks lain.
2. Jika input ambigu, gunakan estimasi terbaik berdasarkan standar porsi katering.
3. Referensi standar:
   - 1 centong nasi = 100g
   - 1 potong ayam goreng sedang = 80g
   - 1 butir telur rebus = 55g
   - 1 iris tipis timun = 5g
   - 1 potong tempe goreng = 50g
   - 1 potong tahu goreng = 40g
   - 1 sendok sayur = 30g
   - 1 buah pisang sedang = 80g
   - 1 gelas air putih = 250g"""


class GramConverterService:
    """Service untuk konversi satuan porsi → gram menggunakan Gemini AI."""

    def __init__(self):
        self._model = None

    def _get_model(self):
        """Lazy-init Gemini model."""
        if self._model is None:
            try:
                import google.generativeai as genai
                genai.configure(api_key=settings.gemini_api_key)
                self._model = genai.GenerativeModel(
                    settings.gemini_text_model,
                    system_instruction=SYSTEM_INSTRUCTION,
                )
            except Exception as e:
                logger.error(f"Gagal init Gemini model: {e}")
                raise
        return self._model

    async def convert_to_grams(self, user_input: str) -> int:
        """
        Konversi deskripsi porsi ke gram menggunakan AI.
        
        Args:
            user_input: "3 iris timun", "1 potong ayam sedang", "2 centong nasi"
            
        Returns:
            Estimasi berat dalam gram (integer)
        """
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY tidak dikonfigurasi")

        model = self._get_model()

        prompt = f"Konversi ke gram: '{user_input}'"

        try:
            response = model.generate_content(prompt)
            raw = response.text.strip()
            
            # Extract number from response (handle cases like "15 gram" or "~15")
            numbers = re.findall(r'\d+', raw)
            if not numbers:
                logger.warning(f"AI tidak mengembalikan angka untuk '{user_input}': '{raw}'")
                raise ValueError(f"AI tidak bisa mengkonversi: '{user_input}'")
            
            grams = int(numbers[0])
            
            # Sanity check: porsi normal katering antara 1-2000 gram
            if grams < 1:
                grams = 1
            elif grams > 5000:
                logger.warning(f"AI mengembalikan {grams}g untuk '{user_input}', capping to 5000")
                grams = 5000

            logger.info(f"GramConverter: '{user_input}' -> {grams}g")
            return grams

        except Exception as e:
            logger.error(f"GramConverter error untuk '{user_input}': {e}")
            raise

    async def calculate_nutrition(
        self,
        food_name: str,
        portion_desc: str,
        tenant_id: str,
        supabase,
    ) -> Dict[str, Any]:
        """
        Hitung nutrisi dengan hybrid approach:
        1. AI convert portion → grams
        2. Lookup nutrition_ref dari DB (per 100g)
        3. Kalkulasi: (grams / 100) × nutrition_per_100g
        """
        full_input = f"{portion_desc} {food_name}"
        estimated_grams = await self.convert_to_grams(full_input)

        nutrition_data = await self._find_nutrition_ref(food_name, supabase)

        if not nutrition_data:
            return {
                "food_name": food_name,
                "portion_desc": portion_desc,
                "estimated_weight_gram": estimated_grams,
                "nutrition_ref_found": False,
                "message": f"Data nutrisi untuk '{food_name}' tidak ditemukan di database TKPI",
                "calories": 0,
                "proteins": 0,
                "fat": 0,
                "carbohydrates": 0,
            }

        factor = estimated_grams / 100.0

        return {
            "food_name": food_name,
            "nutrition_ref_name": nutrition_data.get("name", ""),
            "portion_desc": portion_desc,
            "estimated_weight_gram": estimated_grams,
            "nutrition_ref_found": True,
            "per_100g": {
                "calories": nutrition_data.get("calories", 0),
                "proteins": nutrition_data.get("proteins", 0),
                "fat": nutrition_data.get("fat", 0),
                "carbohydrates": nutrition_data.get("carbohydrates", 0),
            },
            "total_nutrition": {
                "calories": round(factor * float(nutrition_data.get("calories", 0) or 0), 2),
                "proteins": round(factor * float(nutrition_data.get("proteins", 0) or 0), 2),
                "fat": round(factor * float(nutrition_data.get("fat", 0) or 0), 2),
                "carbohydrates": round(factor * float(nutrition_data.get("carbohydrates", 0) or 0), 2),
            },
        }

    async def batch_calculate_nutrition(
        self,
        items: list, # List[Dict[str, str]] with keys: food_name, portion_desc
        tenant_id: str,
        supabase,
    ) -> list:
        """
        Batch process multiple ingredients at once to save AI requests.
        Prompt Gemini to return JSON mapping of original inputs to grams.
        """
        if not items:
            return []
            
        # Compile all descriptions for AI batch prompt
        inputs_dict = {
            f"item_{i}": f"{item['portion_desc']} {item['food_name']}"
            for i, item in enumerate(items)
        }
        
        prompt = (
            "Konversi porsi berikut ke gram.\n"
            f"Inputs: {json.dumps(inputs_dict, ensure_ascii=False)}\n"
            "Kembalikan HANYA JSON berisi key (sama dengan input) dan value (integer gram hitunganmu), tanpa code block atau teks lainnya. "
            "Contoh balasan: {\"item_0\": 100, \"item_1\": 15}"
        )
        
        model = self._get_model()
        results = []
        
        try:
            response = model.generate_content(prompt)
            raw = response.text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            if raw.endswith("```"):
                raw = raw[:-3]
                
            ai_grams = json.loads(raw.strip())
        except Exception as e:
            logger.error(f"Batch GramConverter error: {e}")
            # Fallback to 1 g for parsing failures
            ai_grams = {k: 1 for k in inputs_dict.keys()}
            
        for i, item in enumerate(items):
            food_name = item["food_name"]
            portion_desc = item["portion_desc"]
            key = f"item_{i}"
            
            estimated_grams = int(ai_grams.get(key, 1))
            
            # Lookup DB per 100g
            nutrition_data = await self._find_nutrition_ref(food_name, supabase)
            
            if not nutrition_data:
                results.append({
                    "food_name": food_name,
                    "portion_desc": portion_desc,
                    "estimated_weight_gram": estimated_grams,
                    "nutrition_ref_found": False,
                    "message": f"Data nutrisi untuk '{food_name}' tidak ditemukan di database TKPI",
                    "calories": 0, "proteins": 0, "fat": 0, "carbohydrates": 0,
                })
                continue
                
            factor = estimated_grams / 100.0
            results.append({
                "food_name": food_name,
                "nutrition_ref_name": nutrition_data.get("name", ""),
                "portion_desc": portion_desc,
                "estimated_weight_gram": estimated_grams,
                "nutrition_ref_found": True,
                "per_100g": {
                    "calories": nutrition_data.get("calories", 0),
                    "proteins": nutrition_data.get("proteins", 0),
                    "fat": nutrition_data.get("fat", 0),
                    "carbohydrates": nutrition_data.get("carbohydrates", 0),
                },
                "total_nutrition": {
                    "calories": round(factor * float(nutrition_data.get("calories", 0) or 0), 2),
                    "proteins": round(factor * float(nutrition_data.get("proteins", 0) or 0), 2),
                    "fat": round(factor * float(nutrition_data.get("fat", 0) or 0), 2),
                    "carbohydrates": round(factor * float(nutrition_data.get("carbohydrates", 0) or 0), 2),
                },
            })
            
        return results

    async def _find_nutrition_ref(self, food_name: str, supabase) -> Optional[dict]:
        """
        Cari nutrition_ref yang cocok dengan food_name.
        Strategi: exact match → nutrition_aliases → partial match → AI TKPI resolver.
        """
        name = food_name.strip()
        lower_name = name.lower()

        # 1. Exact match (case-insensitive)
        try:
            resp = (
                supabase.table("nutrition_ref")
                .select("id, name, calories, proteins, fat, carbohydrates")
                .ilike("name", name)
                .limit(1)
                .execute()
            )
            if resp.data:
                return resp.data[0]
        except Exception as e:
            pass

        # 2. Lookup in nutrition_aliases (Learning DB)
        try:
            alias_resp = (
                supabase.table("nutrition_aliases")
                .select("nutrition_ref_id")
                .ilike("slang_name", name)
                .limit(1)
                .execute()
            )
            if alias_resp.data:
                ref_id = alias_resp.data[0]["nutrition_ref_id"]
                n_resp = supabase.table("nutrition_ref").select("id, name, calories, proteins, fat, carbohydrates").eq("id", ref_id).execute()
                if n_resp.data:
                    return n_resp.data[0]
        except Exception as e:
            pass

        # 3. Partial match with wildcard
        try:
            resp = (
                supabase.table("nutrition_ref")
                .select("id, name, calories, proteins, fat, carbohydrates")
                .ilike("name", f"%{name}%")
                .limit(5)
                .execute()
            )
            if resp.data:
                # Pick the shortest match (most specific)
                best = min(resp.data, key=lambda x: len(x.get("name", "")))
                
                # Auto-learn this mapping safely if there wasn't an alias
                try:
                    supabase.table("nutrition_aliases").insert({
                        "slang_name": lower_name,
                        "nutrition_ref_id": best["id"]
                    }).execute()
                except Exception:
                    pass
                    
                return best
        except Exception as e:
            pass

        # 4. AI-assisted lookup — ask Gemini for the official TKPI name
        try:
            model = self._get_model()
            prompt = (
                f"Apa nama resmi bahan makanan '{name}' dalam Tabel Komposisi Pangan Indonesia (TKPI)? "
                f"Balas HANYA dengan nama resminya saja, tanpa penjelasan. Jika tidak tahu, balas 'TIDAK TAHU'."
            )
            response = model.generate_content(prompt)
            tkpi_name = response.text.strip().strip('"').strip("'")
            
            if tkpi_name and tkpi_name.lower() != name.lower() and tkpi_name.lower() != "tidak tahu":
                resp = (
                    supabase.table("nutrition_ref")
                    .select("id, name, calories, proteins, fat, carbohydrates")
                    .ilike("name", f"%{tkpi_name}%")
                    .limit(3)
                    .execute()
                )
                if resp.data:
                    best = min(resp.data, key=lambda x: len(x.get("name", "")))
                    logger.info(f"AI matched '{name}' -> TKPI '{best['name']}'")
                    
                    # Auto-learn AI finding
                    try:
                        supabase.table("nutrition_aliases").insert({
                            "slang_name": lower_name,
                            "nutrition_ref_id": best["id"]
                        }).execute()
                    except Exception:
                        pass
                        
                    return best
        except Exception as e:
            logger.warning(f"AI TKPI lookup gagal: {e}")

        return None


# Singleton instance
gram_converter = GramConverterService()
