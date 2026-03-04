"""
Product management endpoints.
"""

from decimal import Decimal
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query, status

from core.database import get_supabase
from core.dependencies import get_current_user, require_role
from models.product import ProductCreate, ProductResponse, ProductUpdate, StockAdjustRequest
from models.user import UserInDB

router = APIRouter(prefix="/products", tags=["products"])


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

    return {
        "success": True,
        "data": [ProductResponse(**p) for p in data],
        "total": len(data),
    }


@router.post("", response_model=Dict[str, Any], dependencies=[Depends(require_role(["owner", "admin"]))])
def create_product(
    body: ProductCreate,
    current_user: UserInDB = Depends(get_current_user),
):
    """Create new product."""
    supabase = get_supabase()

    response = (
        supabase.table("products")
        .insert(
            {
                "tenant_id": current_user.tenant_id,
                "name": body.name,
                "sku": body.sku,
                "category": body.category,
                "unit": body.unit,
                "hpp": float(body.hpp),
                "sell_price": float(body.sell_price),
                "stock_qty": float(body.stock_qty),
                "stock_min": float(body.stock_min),
                "notes": body.notes,
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
    if body.notes is not None:
        update_data["notes"] = body.notes

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

