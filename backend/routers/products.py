"""
Product management endpoints.
"""

from decimal import Decimal
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query, status

from core.database import get_supabase
from core.dependencies import get_current_user, require_role
from models.product import ProductCreate, ProductResponse, ProductUpdate, StockAdjustRequest, StockManualAdjustRequest
from models.user import UserInDB
from utils.unit_converter import get_base_unit, to_base, to_display

router = APIRouter(prefix="/products", tags=["products"])


def _enrich_product(p: dict) -> dict:
    """Add computed display fields to a product dict."""
    factor = float(p.get("conversion_factor") or 1)
    stock_qty = float(p.get("stock_qty") or 0)
    stock_min = float(p.get("stock_min") or 0)
    p["stock_qty_display"] = round(stock_qty / factor, 3) if factor else stock_qty
    p["stock_min_display"] = round(stock_min / factor, 3) if factor else stock_min
    # Ensure defaults
    if not p.get("base_unit"):
        p["base_unit"] = "gram"
    if not p.get("display_unit"):
        p["display_unit"] = p.get("unit", "pcs")
    if not p.get("conversion_factor"):
        p["conversion_factor"] = 1
    return p


@router.get("", response_model=Dict[str, Any])
def list_products(
    category: str = Query(""),
    search: str = Query(""),
    is_active: bool = Query(True),
    current_user: UserInDB = Depends(get_current_user),
):
    """List products."""
    supabase = get_supabase()
    query = supabase.table("products").select("*").eq("tenant_id", current_user.tenant_id)

    if is_active:
        query = query.eq("is_active", True)

    if category:
        query = query.eq("category", category)

    response = query.execute()
    data = getattr(response, "data", None) or []

    if search:
        data = [p for p in data if search.lower() in p.get("name", "").lower()]

    enriched = [_enrich_product(p) for p in data]

    return {
        "success": True,
        "data": [ProductResponse(**p) for p in enriched],
        "total": len(enriched),
    }


@router.post("", response_model=Dict[str, Any], dependencies=[Depends(require_role(["owner", "admin"]))])
def create_product(
    body: ProductCreate,
    current_user: UserInDB = Depends(get_current_user),
):
    """Create new product."""
    supabase = get_supabase()

    # Determine display/base unit and conversion factor
    disp_unit = body.display_unit or body.unit or "pcs"
    base, factor = get_base_unit(disp_unit)

    # Convert user input (display) to base unit
    stock_qty_base = to_base(float(body.stock_qty), disp_unit, factor)
    stock_min_base = to_base(float(body.stock_min), disp_unit, factor)

    response = (
        supabase.table("products")
        .insert(
            {
                "tenant_id": current_user.tenant_id,
                "name": body.name,
                "sku": body.sku,
                "category": body.category,
                "unit": disp_unit,
                "base_unit": base,
                "display_unit": disp_unit,
                "conversion_factor": factor,
                "hpp": float(body.hpp),
                "sell_price": float(body.sell_price),
                "stock_qty": stock_qty_base,
                "stock_min": stock_min_base,
                "is_active": True,
            }
        )
        .execute()
    )

    data = getattr(response, "data", None) or []
    if not data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create product",
        )

    product_id = data[0]["id"]

    # Insert price history
    if body.hpp > 0:
        supabase.table("price_history").insert(
            {
                "tenant_id": current_user.tenant_id,
                "product_id": product_id,
                "price_type": "hpp",
                "new_price": float(body.hpp),
                "effective_date": "today()",
            }
        ).execute()

    # Insert stock history untuk stok awal
    if body.stock_qty > 0:
        supabase.table("stock_history").insert(
            {
                "tenant_id": current_user.tenant_id,
                "product_id": product_id,
                "change_qty": float(body.stock_qty),
                "balance_after": float(body.stock_qty),
                "reason": "adjustment",
                "notes": "Stok awal",
            }
        ).execute()

    return {"success": True, "data": ProductResponse(**data[0])}


@router.put("/{product_id}", response_model=Dict[str, Any], dependencies=[Depends(require_role(["owner", "admin"]))])
def update_product(
    product_id: str,
    body: ProductUpdate,
    current_user: UserInDB = Depends(get_current_user),
):
    """Update product."""
    supabase = get_supabase()

    update_data = {}
    if body.name is not None:
        update_data["name"] = body.name
    if body.sku is not None:
        update_data["sku"] = body.sku
    if body.category is not None:
        update_data["category"] = body.category
    if body.unit is not None:
        update_data["unit"] = body.unit
    if body.hpp is not None:
        update_data["hpp"] = float(body.hpp)
    if body.sell_price is not None:
        update_data["sell_price"] = float(body.sell_price)
    if body.stock_min is not None:
        update_data["stock_min"] = float(body.stock_min)

    response = (
        supabase.table("products")
        .update(update_data)
        .eq("id", product_id)
        .eq("tenant_id", current_user.tenant_id)
        .execute()
    )

    data = getattr(response, "data", None) or []
    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    # Track price change
    if body.hpp is not None:
        supabase.table("price_history").insert(
            {
                "tenant_id": current_user.tenant_id,
                "product_id": product_id,
                "price_type": "hpp",
                "new_price": float(body.hpp),
                "changed_by": current_user.id,
            }
        ).execute()

    return {"success": True, "data": ProductResponse(**data[0])}


@router.delete("/{product_id}", response_model=Dict[str, Any], dependencies=[Depends(require_role(["owner"]))])
def delete_product(
    product_id: str,
    current_user: UserInDB = Depends(get_current_user),
):
    """Soft delete product."""
    supabase = get_supabase()

    supabase.table("products").update({"is_active": False}).eq("id", product_id).eq(
        "tenant_id", current_user.tenant_id
    ).execute()

    return {"success": True, "message": "Product deleted"}


# ─── GET /products/projection ────────────────────────────────────────────────

@router.get("/projection", response_model=Dict[str, Any])
def get_stock_projection(
    days: int = Query(default=7, ge=1, le=90),
    current_user: UserInDB = Depends(get_current_user),
):
    """
    Proyeksi stok {days} hari ke depan.
    Sumber: menu minggu ini (via BOM) → fallback rata-rata 7 hari terakhir.
    """
    import math
    from datetime import date, timedelta

    supabase = get_supabase()
    tid = current_user.tenant_id
    today = date.today()
    monday = today - timedelta(days=today.weekday())

    # ── Ambil semua produk aktif ──────────────────────────────────────────
    prod_resp = (
        supabase.table("products")
        .select("id, name, unit, stock_qty, stock_min, hpp")
        .eq("tenant_id", tid)
        .eq("is_active", True)
        .execute()
    )
    products = getattr(prod_resp, "data", None) or []
    prod_map = {p["id"]: p for p in products}

    # ── Coba dapatkan menu minggu ini + sekolah ───────────────────────────
    menu_resp = (
        supabase.table("mbg_weekly_menus")
        .select("day_of_week, menu_id")
        .eq("tenant_id", tid)
        .eq("week_start", monday.isoformat())
        .execute()
    )
    weekly = getattr(menu_resp, "data", None) or []

    # Total porsi / hari dari sekolah
    school_resp = (
        supabase.table("schools")
        .select("default_portions")
        .eq("tenant_id", tid)
        .eq("is_active", True)
        .execute()
    )
    total_portions = sum(
        int(s.get("default_portions") or 0)
        for s in (getattr(school_resp, "data", None) or [])
    )

    # Kumpulkan kebutuhan bahan per hari dari BOM
    daily_usage: Dict[str, float] = {}  # product_id → kebutuhan rata2/hari
    based_on_menu = False

    if weekly and total_portions > 0:
        based_on_menu = True
        menu_ids = list({m["menu_id"] for m in weekly if m.get("menu_id")})
        active_days = min(len(weekly), days)

        if menu_ids:
            # Ambil resep (komponen + bahan langsung)
            recipe_resp = (
                supabase.table("recipes")
                .select("menu_id, ingredient_id, component_id, qty_needed")
                .in_("menu_id", menu_ids)
                .execute()
            )
            recipes = getattr(recipe_resp, "data", None) or []

            # Komponen → bahan
            comp_ids = list({r["component_id"] for r in recipes if r.get("component_id")})
            comp_items: list = []
            if comp_ids:
                ci_resp = (
                    supabase.table("recipe_component_items")
                    .select("component_id, ingredient_id, qty_needed")
                    .in_("component_id", comp_ids)
                    .execute()
                )
                comp_items = getattr(ci_resp, "data", None) or []

            comp_ing_map: Dict[str, list] = {}
            for ci in comp_items:
                comp_ing_map.setdefault(ci["component_id"], []).append(ci)

            # Akumulasi kebutuhan per hari
            for menu_row in weekly:
                menu_id = menu_row.get("menu_id")
                if not menu_id:
                    continue
                for r in recipes:
                    if r["menu_id"] != menu_id:
                        continue
                    needed = float(r.get("qty_needed") or 0) * total_portions
                    if r.get("ingredient_id"):
                        iid = r["ingredient_id"]
                        daily_usage[iid] = daily_usage.get(iid, 0) + needed / max(active_days, 1)
                    elif r.get("component_id"):
                        for ci in comp_ing_map.get(r["component_id"], []):
                            iid = ci["ingredient_id"]
                            sub = float(ci.get("qty_needed") or 0) * total_portions
                            daily_usage[iid] = daily_usage.get(iid, 0) + sub / max(active_days, 1)

    if not based_on_menu:
        # Fallback: rata-rata pemakaian 7 hari terakhir
        start7 = (today - timedelta(days=7)).isoformat()
        hist_resp = (
            supabase.table("stock_history")
            .select("product_id, change_qty, reason")
            .eq("tenant_id", tid)
            .gte("created_at", start7)
            .execute()
        )
        for row in (getattr(hist_resp, "data", None) or []):
            if row.get("reason") in ("production", "mbg_production", "serah"):
                delta = abs(float(row.get("change_qty") or 0))
                pid = row["product_id"]
                daily_usage[pid] = daily_usage.get(pid, 0) + delta / 7

    # ── Susun hasil proyeksi ──────────────────────────────────────────────
    items_out = []
    for p in products:
        pid = p["id"]
        stock = float(p.get("stock_qty") or 0)
        stock_min = float(p.get("stock_min") or 0)
        usage = daily_usage.get(pid, 0)
        needed_period = usage * days

        if usage > 0:
            days_rem = stock / usage
        else:
            days_rem = 999  # tak terbatas

        sufficient = stock >= needed_period
        shortage = max(needed_period - stock, 0)

        if stock <= 0:
            stat = "habis"
        elif days_rem < 1:
            stat = "kritis"
        elif days_rem <= 7:
            stat = "menipis"
        else:
            stat = "aman"

        items_out.append({
            "product_id": pid,
            "name": p["name"],
            "unit": p["unit"],
            "stock_qty": stock,
            "stock_min": stock_min,
            "daily_usage": round(usage, 4),
            "days_remaining": round(min(days_rem, 999), 1),
            "needed_for_period": round(needed_period, 3),
            "sufficient": sufficient,
            "shortage": round(shortage, 3),
            "status": stat,
            "hpp": p.get("hpp"),
        })

    # Sort: kritis/habis dulu
    order = {"habis": 0, "kritis": 1, "menipis": 2, "aman": 3}
    items_out.sort(key=lambda x: order.get(x["status"], 4))

    summary = {
        "total_items": len(items_out),
        "sufficient_count": sum(1 for i in items_out if i["status"] == "aman"),
        "warning_count": sum(1 for i in items_out if i["status"] == "menipis"),
        "critical_count": sum(1 for i in items_out if i["status"] in ("kritis", "habis")),
    }

    return {
        "success": True,
        "data": {
            "projection_days": days,
            "based_on_menu": based_on_menu,
            "items": items_out,
            "summary": summary,
        },
    }



@router.get("/low-stock", response_model=Dict[str, Any])
def get_low_stock_products(current_user: UserInDB = Depends(get_current_user)):
    """Get products with low stock."""
    supabase = get_supabase()

    # Query semua produk
    response = (
        supabase.table("products")
        .select("*")
        .eq("tenant_id", current_user.tenant_id)
        .eq("is_active", True)
        .execute()
    )

    data = getattr(response, "data", None) or []

    # Filter yang stock_qty <= stock_min
    low_stock = [p for p in data if Decimal(str(p["stock_qty"])) <= Decimal(str(p["stock_min"]))]

    return {
        "success": True,
        "data": [ProductResponse(**p) for p in low_stock],
        "total": len(low_stock),
    }


@router.post("/{product_id}/adjust-stock", response_model=Dict[str, Any], dependencies=[Depends(require_role(["owner", "admin"]))])
def adjust_stock(
    product_id: str,
    body: StockAdjustRequest,
    current_user: UserInDB = Depends(get_current_user),
):
    """Adjust product stock."""
    supabase = get_supabase()

    # Get current product
    product_resp = (
        supabase.table("products")
        .select("stock_qty")
        .eq("id", product_id)
        .eq("tenant_id", current_user.tenant_id)
        .single()
        .execute()
    )

    product_data = getattr(product_resp, "data", None)
    if not product_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    current_qty = Decimal(str(product_data["stock_qty"]))
    new_qty = current_qty + body.change_qty
    if new_qty < 0:
        new_qty = Decimal("0.000")

    # Update product stock
    supabase.table("products").update({"stock_qty": float(new_qty)}).eq("id", product_id).execute()

    # Insert stock history
    supabase.table("stock_history").insert(
        {
            "tenant_id": current_user.tenant_id,
            "product_id": product_id,
            "change_qty": float(body.change_qty),
            "balance_after": float(new_qty),
            "reason": body.reason,
            "notes": body.notes,
        }
    ).execute()

    # If spoilage/waste, insert cashflow
    if body.reason in ["spoilage", "waste"]:
        supabase.table("cashflow_log").insert(
            {
                "tenant_id": current_user.tenant_id,
                "flow_type": "out",
                "category": f"{body.reason}_loss",
                "amount": 0,  # Placeholder
                "description": f"{body.reason}: {body.notes}",
            }
        ).execute()

    return {"success": True, "data": {"new_stock_qty": float(new_qty)}}


# ─── GET /products/{product_id}/history ──────────────────────────────────────

@router.get("/{product_id}/history", response_model=Dict[str, Any])
def get_product_history(
    product_id: str,
    limit: int = Query(default=50),
    offset: int = Query(default=0),
    current_user: UserInDB = Depends(get_current_user),
):
    """
    Riwayat perubahan stok suatu produk.
    Hitung running_balance dari oldest ke newest.
    """
    supabase = get_supabase()
    tid = current_user.tenant_id

    # Cek produk ada + filter tenant
    prod_resp = (
        supabase.table("products")
        .select("id, name, unit, stock_qty")
        .eq("id", product_id)
        .eq("tenant_id", tid)
        .single()
        .execute()
    )
    product = getattr(prod_resp, "data", None)
    if not product:
        raise HTTPException(status_code=404, detail="Produk tidak ditemukan")

    # Ambil semua history (untuk hitung running balance), sorted ASC
    hist_resp = (
        supabase.table("stock_history")
        .select("id, change_qty, balance_after, reason, notes, created_at")
        .eq("product_id", product_id)
        .eq("tenant_id", tid)
        .order("created_at", desc=False)
        .execute()
    )
    all_rows = getattr(hist_resp, "data", None) or []
    total = len(all_rows)

    # Paginated slice
    paged = all_rows[offset: offset + limit]

    # Running balance: jika ada balance_after pakai itu, jika tidak hitung manual
    running = Decimal("0")
    if all_rows:
        try:
            # Seed dari baris paling awal
            running = Decimal(str(all_rows[0].get("balance_after") or 0)) - Decimal(
                str(all_rows[0].get("change_qty") or 0)
            )
        except Exception:
            running = Decimal("0")

    # Rebuild running balance for all_rows up to paged range
    balance_map: dict = {}
    r = Decimal("0")
    for row in all_rows:
        try:
            ba = row.get("balance_after")
            if ba is not None:
                r = Decimal(str(ba))
            else:
                r += Decimal(str(row.get("change_qty") or 0))
        except Exception:
            pass
        balance_map[row["id"]] = r

    history = [
        {
            "id": row.get("id"),
            "change_qty": str(row.get("change_qty", 0)),
            "balance_after": str(row.get("balance_after") or balance_map.get(row["id"], 0)),
            "running_balance": str(balance_map.get(row["id"], 0)),
            "reason": row.get("reason"),
            "notes": row.get("notes"),
            "created_at": row.get("created_at"),
        }
        for row in paged
    ]

    return {
        "success": True,
        "data": {
            "product": product,
            "history": history,
            "total": total,
        },
    }


# ─── POST /products/{product_id}/adjust-stock-manual ─────────────────────────

@router.post(
    "/{product_id}/adjust-stock-manual",
    response_model=Dict[str, Any],
    dependencies=[Depends(require_role(["owner", "admin"]))],
)
def adjust_stock_manual(
    product_id: str,
    body: StockManualAdjustRequest,
    current_user: UserInDB = Depends(get_current_user),
):
    """
    Koreksi stok manual — menerima stok fisik aktual (new_qty), bukan delta.
    Menghitung delta, update produk, insert stock_history & audit_log.
    """
    supabase = get_supabase()
    tid = current_user.tenant_id

    # Ambil produk saat ini
    prod_resp = (
        supabase.table("products")
        .select("id, name, stock_qty, unit")
        .eq("id", product_id)
        .eq("tenant_id", tid)
        .single()
        .execute()
    )
    prod = getattr(prod_resp, "data", None)
    if not prod:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produk tidak ditemukan")

    old_qty = Decimal(str(prod["stock_qty"] or 0))
    new_qty = Decimal(str(body.new_qty))
    delta = new_qty - old_qty

    # Update stok produk
    supabase.table("products").update({"stock_qty": float(new_qty)}).eq("id", product_id).execute()

    # Insert stock_history
    supabase.table("stock_history").insert({
        "tenant_id": tid,
        "product_id": product_id,
        "change_qty": float(delta),
        "balance_after": float(new_qty),
        "reason": "adjustment",
        "notes": f"Koreksi manual: {body.reason}" + (f". {body.notes}" if body.notes else ""),
    }).execute()

    # Insert audit_log
    try:
        supabase.table("audit_log").insert({
            "tenant_id": tid,
            "user_id": current_user.id,
            "action": "stock_adjustment",
            "resource": "products",
            "resource_id": product_id,
            "old_data": {"stock_qty": float(old_qty)},
            "new_data": {"stock_qty": float(new_qty), "delta": float(delta), "reason": body.reason},
        }).execute()
    except Exception:
        pass  # audit_log non-fatal

    return {
        "success": True,
        "data": {
            "product_id": product_id,
            "name": prod["name"],
            "unit": prod["unit"],
            "old_qty": float(old_qty),
            "new_qty": float(new_qty),
            "delta": float(delta),
        },
    }
