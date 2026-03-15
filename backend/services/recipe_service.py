"""
backend/services/recipe_service.py
Kalkulasi dan pemotongan stok BOM (Bill of Material) untuk produksi MBG — Modul 10

calculate() → cek apakah stok cukup untuk produksi N porsi (expand komponen)
deduct_stock() → potong stok secara atomik via increment_stock RPC (expand komponen)
"""

import logging
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class RecipeService:
    """Service untuk BOM calculation dan stock deduction."""

    def _flatten_recipes(
        self,
        recipes: List[dict],
        qty: int,
        supabase,
    ) -> Dict[str, Decimal]:
        """
        Flatten recipe list into {ingredient_id: total_qty}.
        Expands components, deduplicates ingredients by summing quantities.
        """
        flat: Dict[str, Decimal] = {}

        for r in recipes:
            if r.get("component_id"):
                # ─── Expand component ────────────────────────────────
                comp_items_resp = (
                    supabase.table("recipe_component_items")
                    .select("ingredient_id, qty_needed")
                    .eq("component_id", r["component_id"])
                    .execute()
                )
                comp_items = getattr(comp_items_resp, "data", None) or []

                recipe_qty = Decimal(str(r.get("qty_needed", 1)))
                for item in comp_items:
                    ing_id = item["ingredient_id"]
                    needed = Decimal(str(item["qty_needed"])) * recipe_qty * Decimal(str(qty))
                    flat[ing_id] = flat.get(ing_id, Decimal("0")) + needed
            else:
                # ─── Direct ingredient ───────────────────────────────
                ing_id = r.get("ingredient_id") or r.get("product_id")
                if not ing_id:
                    continue
                qty_per_portion = Decimal(str(r.get("qty_needed") or r.get("qty", 0)))
                needed = qty_per_portion * Decimal(str(qty))
                flat[ing_id] = flat.get(ing_id, Decimal("0")) + needed

        return flat

    def calculate(
        self,
        menu_id: str,
        qty: int,
        tenant_id: str,
        supabase,
    ) -> Dict[str, Any]:
        """
        Cek apakah stok bahan cukup untuk produksi qty porsi dari menu_id.
        Expands components → flattens → deduplicates → checks stock.
        Return: {can_produce, max_possible, has_bom, ingredients: [...]}
        """
        # Query recipes (BOM) untuk menu ini
        recipes_resp = (
            supabase.table("recipes")
            .select("*")
            .eq("menu_id", menu_id)
            .eq("tenant_id", tenant_id)
            .execute()
        )
        recipes: List[dict] = getattr(recipes_resp, "data", None) or []

        if not recipes:
            return {
                "can_produce": True,
                "max_possible": qty,
                "has_bom": False,
                "ingredients": [],
            }

        # Flatten (expand components + direct ingredients)
        flat = self._flatten_recipes(recipes, qty, supabase)

        if not flat:
            return {
                "can_produce": True,
                "max_possible": qty,
                "has_bom": False,
                "ingredients": [],
            }

        ingredients = []
        can_produce = True
        max_possible = qty

        for ing_id, total_needed in flat.items():
            try:
                product_resp = (
                    supabase.table("products")
                    .select("id, name, stock_qty, unit")
                    .eq("id", ing_id)
                    .single()
                    .execute()
                )
                product = getattr(product_resp, "data", None) or {}
            except Exception:
                product = {}

            available = Decimal(str(product.get("stock_qty", 0)))
            sufficient = available >= total_needed
            shortage = max(Decimal("0"), total_needed - available)

            if not sufficient:
                can_produce = False
                qty_per_portion = total_needed / Decimal(str(qty)) if qty > 0 else Decimal("0")
                if qty_per_portion > 0:
                    possible_from_this = int(available / qty_per_portion)
                    max_possible = min(max_possible, possible_from_this)

            ingredients.append({
                "ingredient_id": ing_id,
                "name": product.get("name", "?"),
                "unit": product.get("unit") or "kg",
                "qty_needed_per_portion": float(total_needed / Decimal(str(qty))) if qty > 0 else 0,
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
        Expands components → flattens → deduplicates → deducts.
        Insert stock_history per bahan.
        Return: list stock_history records yang dibuat.
        """
        recipes_resp = (
            supabase.table("recipes")
            .select("*")
            .eq("menu_id", menu_id)
            .eq("tenant_id", tenant_id)
            .execute()
        )
        recipes: List[dict] = getattr(recipes_resp, "data", None) or []

        # Flatten with qty=qty (total needed, not per-portion)
        flat = self._flatten_recipes(recipes, qty, supabase)

        histories = []
        for product_id, total_needed in flat.items():
            delta = float(-total_needed)

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
