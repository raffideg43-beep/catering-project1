"""
backend/services/alias_service.py
Resolusi alias nama item nota → produk DB — Modul 7

Langkah 1: Cek tabel product_aliases (DB lookup exact/ILIKE)
Langkah 2: Jika tidak ketemu → tanya Gemini, auto-save jika confidence >= 0.8
Langkah 3: Jika < 0.8 → tandai needs_confirmation
"""

import json
import logging
import re
from typing import Optional

import httpx

from core.config import settings

logger = logging.getLogger(__name__)


class AliasService:
    """
    Sync service — dipanggil dari RQ worker context.
    """

    def __init__(self) -> None:
        self.api_key = settings.gemini_api_key
        self.model = settings.gemini_text_model
        self.api_url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )
        self._products_cache: dict = {}  # {tenant_id: [(id, name)]}

    def resolve(self, nama_item: str, tenant_id: str, supabase) -> dict:
        """
        Return dict:
          {product_id, product_name, confidence, source, needs_confirmation}
        """
        # ─── Langkah 0: Cek product utama (exact / case-insensitive) via memory ───
        products = self._get_products(tenant_id, supabase)
        for p in products:
            if p["name"].lower() == nama_item.lower():
                logger.info(f"Main product match: '{nama_item}' → '{p['name']}'")
                return {
                    "product_id": p["id"],
                    "product_name": p["name"],
                    "confidence": 1.0,
                    "source": "exact_match",
                    "needs_confirmation": False,
                }

        # ─── Langkah 1: Cek product_aliases (DB) ───
        alias_resp = (
            supabase.table("product_aliases")
            .select("product_id, products!product_id(name)")
            .eq("tenant_id", tenant_id)
            .ilike("alias_name", nama_item)
            .limit(1)
            .execute()
        )
        aliases = getattr(alias_resp, "data", None) or []
        if aliases:
            row = aliases[0]
            prod_name = (row.get("products") or {}).get("name", nama_item)
            logger.info(f"Alias DB match: '{nama_item}' → '{prod_name}'")
            return {
                "product_id": row["product_id"],
                "product_name": prod_name,
                "confidence": 1.0,
                "source": "alias_db",
                "needs_confirmation": False,
            }

        # ─── Langkah 2: AI matching via Gemini ───
        if not products:
            return self._unresolved(nama_item)

        product_list = "\n".join([f"- id:{p['id']} name:{p['name']}" for p in products])
        prompt = (
            f"Dari daftar produk ini:\n{product_list}\n\n"
            f"Nama item '{nama_item}' paling cocok ke produk mana?\n"
            "Return JSON SAJA:\n"
            '{"product_id": "uuid atau null", '
            '"product_name": "nama atau null", '
            '"confidence": 0.0}\n'
            "Jika tidak ada yang cocok: confidence = 0"
        )

        result = self._ask_gemini(prompt)
        if not result:
            return self._unresolved(nama_item)

        confidence = float(result.get("confidence", 0))
        product_id = result.get("product_id")
        product_name = result.get("product_name")

        if confidence >= 0.8 and product_id:
            # Auto-save alias
            try:
                supabase.table("product_aliases").upsert(
                    {
                        "tenant_id": tenant_id,
                        "product_id": product_id,
                        "alias_name": nama_item,
                        "source": "ai",
                        "confidence": confidence,
                    },
                    on_conflict="tenant_id,alias_name",
                ).execute()
            except Exception as e:
                logger.warning(f"Alias save failed: {e}")

            logger.info(f"AI alias auto-saved: '{nama_item}' → '{product_name}' ({confidence:.0%})")
            return {
                "product_id": product_id,
                "product_name": product_name,
                "confidence": confidence,
                "source": "ai_auto",
                "needs_confirmation": False,
            }

        # Confidence rendah — tandai perlu konfirmasi
        suggestions = []
        if product_id and confidence > 0:
            suggestions = [{"product_id": product_id, "name": product_name, "confidence": confidence}]

        return {
            "product_id": None,
            "product_name": None,
            "confidence": confidence,
            "source": "ai_low_confidence",
            "needs_confirmation": True,
            "suggestions": suggestions,
        }

    def _get_products(self, tenant_id: str, supabase) -> list:
        """Ambil produk tenant dengan cache per request."""
        if tenant_id in self._products_cache:
            return self._products_cache[tenant_id]
        resp = (
            supabase.table("products")
            .select("id, name, category")
            .eq("tenant_id", tenant_id)
            .eq("is_active", True)
            .limit(200)
            .execute()
        )
        products = getattr(resp, "data", None) or []
        self._products_cache[tenant_id] = products
        return products

    def _ask_gemini(self, prompt: str) -> Optional[dict]:
        """Kirim prompt ke Gemini, return parsed dict atau None."""
        if not self.api_key:
            return None
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 256},
        }
        try:
            with httpx.Client(timeout=30) as client:
                resp = client.post(self.api_url, json=payload)
                resp.raise_for_status()
                text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                text = re.sub(r"```json\s*|```\s*", "", text).strip()
                return json.loads(text)
        except Exception as e:
            logger.warning(f"Gemini alias error: {e}")
            return None

    @staticmethod
    def _unresolved(nama_item: str) -> dict:
        return {
            "product_id": None,
            "product_name": nama_item,
            "confidence": 0.0,
            "source": "unresolved",
            "needs_confirmation": True,
            "suggestions": [],
        }


alias_service = AliasService()
