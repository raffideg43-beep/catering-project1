"""
backend/services/recipe_service.py
Kalkulasi dan pemotongan stok BOM (Bill of Material) untuk produksi MBG — Modul 10

calculate() → cek apakah stok cukup untuk produksi N porsi
deduct_stock() → potong stok secara atomik via increment_stock RPC
"""

import logging
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class RecipeService:
    """Service untuk BOM calculation dan stock deduction."""

    def calculate(
        self,
        menu_id: str,
        qty: int,
        tenant_id: str,
        supabase,
    ) -> Dict[str, Any]:
        """
        Cek apakah stok bahan cukup untuk produksi qty porsi dari menu_id.
        Return: {can_produce, max_possible, ingredients: [...]}
        """
        # Query recipes (BOM) untuk menu ini
        recipes_resp = (
            supabase.table("recipes")
            .select("*, products(id, name, stock_qty, unit)")
            .eq("menu_id", menu_id)
            .eq("tenant_id", tenant_id)
            .execute()
        )
        recipes: List[dict] = getattr(recipes_resp, "data", None) or []

        if not recipes:
            # Tidak ada BOM — produksi tidak bisa dicek
            return {
                "can_produce": True,
                "max_possible": qty,
                "has_bom": False,
                "ingredients": [],
            }

        ingredients = []
        can_produce = True
        max_possible = qty  # akan diperkecil jika stok kurang

        for r in recipes:
            qty_per_portion = Decimal(str(r.get("qty_needed") or r.get("qty", 0)))
            total_needed = qty_per_portion * Decimal(str(qty))
            product = r.get("products") or {}
            available = Decimal(str(product.get("stock_qty") or 0))
            sufficient = available >= total_needed
            shortage = max(Decimal("0"), total_needed - available)

            if not sufficient:
                can_produce = False
                # Hitung max possible dari bahan ini
                if qty_per_portion > 0:
                    possible_from_this = int(available / qty_per_portion)
                    max_possible = min(max_possible, possible_from_this)

            ingredients.append({
                "ingredient_id": r.get("ingredient_id") or r.get("product_id"),
                "name": product.get("name", "?"),
                "unit": product.get("unit") or r.get("unit", "kg"),
                "qty_needed_per_portion": float(qty_per_portion),
                "total_needed": float(total_needed),
                "available": float(available),
                "sufficient": sufficient,
                "shortage": float(shortage),
            })

        return {
            "can_produce": can_produce,
            "max_possible": max_possible if can_produce else max_possible,
            "has_bom": True,
            "ingredients": ingredients,
        }

    def deduct_stock(
        self,
        menu_id: str,
        qty: int,
        tenant_id: str,
        supabase,
        delivery_date: date,
    ) -> List[dict]:
        """
        Potong stok atomik via RPC increment_stock (delta negatif).
        Insert stock_history per bahan.
        Return: list stock_history records yang dibuat.
        """
        recipes_resp = (
            supabase.table("recipes")
            .select("*, products(id, name, stock_qty, unit)")
            .eq("menu_id", menu_id)
            .eq("tenant_id", tenant_id)
            .execute()
        )
        recipes: List[dict] = getattr(recipes_resp, "data", None) or []

        histories = []
        for r in recipes:
            product = r.get("products") or {}
            product_id = product.get("id") or r.get("ingredient_id") or r.get("product_id")
            if not product_id:
                continue

            qty_per_portion = Decimal(str(r.get("qty_needed") or r.get("qty", 0)))
            delta = float(-(qty_per_portion * Decimal(str(qty))))

            try:
                # Delta negatif = kurangi stok
                supabase.rpc("increment_stock", {
                    "p_product_id": product_id,
                    "p_delta": delta,
                    "p_tenant_id": tenant_id,
                }).execute()

                # Baca saldo terbaru
                bal_resp = (
                    supabase.table("products")
                    .select("stock_qty")
                    .eq("id", product_id)
                    .single()
                    .execute()
                )
                balance = float((getattr(bal_resp, "data", None) or {}).get("stock_qty", 0))

                hist = supabase.table("stock_history").insert({
                    "tenant_id": tenant_id,
                    "product_id": product_id,
                    "change_qty": str(delta),
                    "balance_after": str(balance),
                    "reason": "production",
                    "notes": f"MBG {delivery_date}: {qty} porsi",
                }).execute()

                histories.append((getattr(hist, "data", None) or [{}])[0])
            except Exception as e:
                logger.error(f"deduct_stock gagal untuk product {product_id}: {e}")
                raise  # re-raise agar caller bisa rollback

        return histories


recipe_service = RecipeService()
