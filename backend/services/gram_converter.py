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
        
        Args:
            food_name: Nama bahan (e.g. "timun", "beras", "ayam")
            portion_desc: Deskripsi porsi (e.g. "3 iris", "1 potong sedang")
            tenant_id: Tenant ID
            supabase: Supabase client
        
        Returns:
            Dict with estimated_weight, calories, proteins, fat, carbs, etc.
        """
        # 1. AI → gram
        full_input = f"{portion_desc} {food_name}"
        estimated_grams = await self.convert_to_grams(full_input)

        # 2. Lookup nutrition_ref by name (case-insensitive, fuzzy)
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

        # 3. Kalkulasi: (gram / 100) × nilai per 100g
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

    async def _find_nutrition_ref(self, food_name: str, supabase) -> Optional[dict]:
        """
        Cari nutrition_ref yang cocok dengan food_name.
        Strategi: exact match → ilike → partial match.
        """
        name = food_name.strip()

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
            logger.warning(f"nutrition_ref exact lookup gagal: {e}")

        # 2. Partial match with wildcard
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
                return best
        except Exception as e:
            logger.warning(f"nutrition_ref partial lookup gagal: {e}")

        # 3. AI-assisted lookup — ask Gemini for the official TKPI name
        try:
            model = self._get_model()
            prompt = (
                f"Apa nama resmi bahan makanan '{name}' dalam Tabel Komposisi Pangan Indonesia (TKPI)? "
                f"Balas HANYA dengan nama resminya saja, tanpa penjelasan."
            )
            response = model.generate_content(prompt)
            tkpi_name = response.text.strip().strip('"').strip("'")
            
            if tkpi_name and tkpi_name.lower() != name.lower():
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
                    return best
        except Exception as e:
            logger.warning(f"AI TKPI lookup gagal: {e}")

        return None


# Singleton instance
gram_converter = GramConverterService()
