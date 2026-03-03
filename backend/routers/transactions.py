"""
backend/routers/transactions.py
Endpoints untuk transaksi — Modul 7

Routes:
  POST /transactions/from-photo     → upload foto, push OCR job
  POST /transactions/{id}/confirm   → konfirmasi: update stok, cashflow
  GET  /transactions                → list dengan filter
  GET  /transactions/{id}           → detail + items
  PUT  /transactions/{id}           → edit header
  DELETE /transactions/{id}         → soft delete (status=voided)
"""

import uuid
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)

from core.database import get_supabase
from core.dependencies import get_current_user, require_role
from models.transaction import (
    ConfirmTransactionRequest,
    PhotoUploadResponse,
    TransactionUpdate,
)
from models.user import UserInDB
from workers.ocr_worker import enqueue_ocr_job

router = APIRouter(tags=["transactions"])

# Max upload size: 10 MB
MAX_PHOTO_BYTES = 10 * 1024 * 1024
ALLOWED_MIME = {"image/jpeg", "image/png", "image/jpg", "image/webp"}


# ─── POST /transactions/from-photo ───────────────────────────────────────────

@router.post(
    "/from-photo",
    response_model=Dict[str, Any],
    dependencies=[Depends(require_role(["owner", "admin", "kasir"]))],
)
async def upload_photo(
    file: UploadFile = File(...),
    current_user: UserInDB = Depends(get_current_user),
):
    """
    Terima foto nota, upload ke Supabase Storage,
    push async OCR job ke Redis, return transaction_id segera.
    """
    supabase = get_supabase()

    # ─── Validasi file ───────────────────────────────────────────────
    content_type = file.content_type or ""
    if content_type not in ALLOWED_MIME:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"File harus berupa gambar JPEG/PNG. Diterima: {content_type}",
        )

    image_bytes = await file.read()
    if len(image_bytes) > MAX_PHOTO_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Ukuran foto maks 10 MB",
        )

    # ─── Upload ke Supabase Storage ──────────────────────────────────
    period_folder = date.today().strftime("%Y-%m")
    ext = "jpg" if "jpeg" in content_type or "jpg" in content_type else "png"
    file_name = f"{uuid.uuid4()}.{ext}"
    storage_path = f"{current_user.tenant_id}/notas/{period_folder}/{file_name}"

    try:
        supabase.storage.from_("nota-photos").upload(
            path=storage_path,
            file=image_bytes,
            file_options={"content-type": content_type},
        )
        # Ambil public URL
        url_resp = supabase.storage.from_("nota-photos").get_public_url(storage_path)
        photo_url = url_resp if isinstance(url_resp, str) else str(url_resp)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload foto gagal: {e}",
        )

    # ─── Insert transaksi dengan status "processing" ──────────────────
    trx_data = {
        "tenant_id": current_user.tenant_id,
        "user_id": current_user.id,
        "type": "expense",
        "source": "telegram_photo",
        "status": "processing",
        "photo_url": photo_url,
        "date": date.today().isoformat(),
        "total": "0.00",
        "pph22_amount": "0.00",   # PPh22 dihitung saat laporan, bukan di sini
        "ppn_amount": "0.00",
        "subtotal": "0.00",
        "discount": "0.00",
    }
    resp = supabase.table("transactions").insert(trx_data).execute()
    data = getattr(resp, "data", None) or []
    if not data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gagal membuat record transaksi",
        )
    trx_id: str = data[0]["id"]

    # ─── Push OCR job ke Redis queue ─────────────────────────────────
    telegram_id: int = current_user.telegram_id or 0
    try:
        enqueue_ocr_job(
            trx_id=trx_id,
            photo_url=photo_url,
            tenant_id=current_user.tenant_id,
            telegram_id=telegram_id,
        )
    except Exception as e:
        # Queue unavailable — update status failed agar user tahu
        supabase.table("transactions").update({"status": "failed"}).eq(
            "id", trx_id
        ).execute()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"OCR queue tidak tersedia: {e}",
        )

    return {
        "success": True,
        "data": PhotoUploadResponse(
            transaction_id=trx_id,
            message="Foto diterima, sedang diproses... Kami akan kabari setelah selesai.",
        ).model_dump(),
    }


# ─── POST /transactions/{id}/confirm ─────────────────────────────────────────

@router.post(
    "/{trx_id}/confirm",
    response_model=Dict[str, Any],
    dependencies=[Depends(require_role(["owner", "admin", "kasir"]))],
)
def confirm_transaction(
    trx_id: str,
    body: ConfirmTransactionRequest = ConfirmTransactionRequest(),
    current_user: UserInDB = Depends(get_current_user),
):
    """
    Konfirmasi nota:
      1. Update status = confirmed
      2. Update stok ATOMIC per item yang punya product_id
      3. Insert cashflow_log
      4. Jika hutang → insert payables
    """
    supabase = get_supabase()

    # ─── Ambil transaksi ─────────────────────────────────────────────
    trx_resp = (
        supabase.table("transactions")
        .select("*")
        .eq("id", trx_id)
        .eq("tenant_id", current_user.tenant_id)
        .single()
        .execute()
    )
    trx = getattr(trx_resp, "data", None)
    if not trx:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaksi tidak ditemukan")
    if trx.get("is_locked"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Transaksi terkunci")
    if trx.get("status") not in ("pending_confirm", "processing"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Status harus pending_confirm, saat ini: {trx.get('status')}",
        )

    # ─── Ambil items ──────────────────────────────────────────────────
    items_resp = (
        supabase.table("transaction_items")
        .select("*")
        .eq("transaction_id", trx_id)
        .execute()
    )
    items: List[dict] = getattr(items_resp, "data", None) or []

    # ─── Update status ke confirmed ───────────────────────────────────
    supabase.table("transactions").update({
        "status": "confirmed",
        "notes": body.notes or trx.get("notes"),
    }).eq("id", trx_id).execute()

    # ─── Update stok ATOMIC via RPC ────────────────────────────────────
    stok_errors: List[str] = []
    for item in items:
        product_id = item.get("product_id")
        if not product_id:
            continue
        qty = Decimal(str(item.get("qty", 0)))
        if qty <= 0:
            continue
        try:
            # Stok KELUAR (pembelian bahan = stok masuk) → delta positif
            supabase.rpc("increment_stock", {
                "p_product_id": product_id,
                "p_delta": float(qty),
                "p_tenant_id": current_user.tenant_id,
            }).execute()

            # Insert stock_history (immutable log)
            balance_resp = (
                supabase.table("products")
                .select("stock_qty")
                .eq("id", product_id)
                .eq("tenant_id", current_user.tenant_id)
                .single()
                .execute()
            )
            balance = float((getattr(balance_resp, "data", None) or {}).get("stock_qty", 0))
            supabase.table("stock_history").insert({
                "tenant_id": current_user.tenant_id,
                "product_id": product_id,
                "transaction_id": trx_id,
                "change_qty": str(qty),
                "balance_after": str(balance),
                "reason": "purchase",
                "notes": f"Konfirmasi nota {trx.get('ref_number', '')}",
            }).execute()
        except Exception as e:
            stok_errors.append(f"{item.get('product_name', '?')}: {e}")

    # ─── Insert cashflow_log (arus kas keluar) ────────────────────────
    try:
        supabase.table("cashflow_log").insert({
            "tenant_id": current_user.tenant_id,
            "transaction_id": trx_id,
            "flow_type": "out",
            "category": "purchase",
            "amount": trx.get("total", "0.00"),
            "description": f"Nota {trx.get('ref_number', trx_id[:8])}",
            "date": trx.get("date") or date.today().isoformat(),
        }).execute()
    except Exception as e:
        pass  # non-fatal

    # ─── Jika hutang → insert payables ───────────────────────────────
    if trx.get("payment_method") == "hutang" or trx.get("payment_status") == "belum_lunas":
        try:
            # Cari nama supplier
            supplier_name = trx.get("nama_toko", "Supplier")
            if trx.get("supplier_id"):
                sup_resp = (
                    supabase.table("suppliers")
                    .select("name")
                    .eq("id", trx["supplier_id"])
                    .single()
                    .execute()
                )
                supplier_name = (getattr(sup_resp, "data", None) or {}).get("name", supplier_name)

            supabase.table("payables").insert({
                "tenant_id": current_user.tenant_id,
                "supplier_id": trx.get("supplier_id"),
                "transaction_id": trx_id,
                "supplier_name": supplier_name,
                "amount": trx.get("total", "0.00"),
                "paid_amount": "0.00",
                "due_date": trx.get("due_date"),
                "status": "unpaid",
            }).execute()
        except Exception as e:
            pass  # non-fatal

    result = {"success": True, "transaction_id": trx_id, "status": "confirmed"}
    if stok_errors:
        result["stok_warnings"] = stok_errors
    return result


# ─── GET /transactions ────────────────────────────────────────────────────────

@router.get("", response_model=Dict[str, Any])
def list_transactions(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    current_user: UserInDB = Depends(get_current_user),
):
    """List transaksi dengan filter dan paginasi."""
    supabase = get_supabase()

    q = (
        supabase.table("transactions")
        .select("*", count="exact")
        .eq("tenant_id", current_user.tenant_id)
        .order("created_at", desc=True)
    )

    if date_from:
        q = q.gte("date", date_from)
    if date_to:
        q = q.lte("date", date_to)
    if status:
        q = q.eq("status", status)
    if type:
        q = q.eq("type", type)
    if search:
        q = q.ilike("nama_toko", f"%{search}%")

    resp = q.range(offset, offset + limit - 1).execute()
    data = getattr(resp, "data", None) or []
    count = getattr(resp, "count", len(data))

    return {
        "success": True,
        "total": count,
        "limit": limit,
        "offset": offset,
        "data": data,
    }


# ─── GET /transactions/{id} ───────────────────────────────────────────────────

@router.get("/{trx_id}", response_model=Dict[str, Any])
def get_transaction(
    trx_id: str,
    current_user: UserInDB = Depends(get_current_user),
):
    """Detail transaksi + items + validation flags."""
    supabase = get_supabase()

    trx_resp = (
        supabase.table("transactions")
        .select("*")
        .eq("id", trx_id)
        .eq("tenant_id", current_user.tenant_id)
        .single()
        .execute()
    )
    trx = getattr(trx_resp, "data", None)
    if not trx:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaksi tidak ditemukan")

    items_resp = (
        supabase.table("transaction_items")
        .select("*")
        .eq("transaction_id", trx_id)
        .execute()
    )
    items = getattr(items_resp, "data", None) or []

    val_resp = (
        supabase.table("nota_validations")
        .select("flags, result")
        .eq("transaction_id", trx_id)
        .limit(1)
        .execute()
    )
    val_rows = getattr(val_resp, "data", None) or []
    val_data = val_rows[0] if val_rows else {}

    trx["items"] = items
    trx["validation_result"] = val_data.get("result")
    trx["validation_flags"] = (val_data.get("flags") or {}).get("flags", [])
    trx["validation_warnings"] = (val_data.get("flags") or {}).get("warnings", [])

    return {"success": True, "data": trx}


# ─── PUT /transactions/{id} ───────────────────────────────────────────────────

@router.put(
    "/{trx_id}",
    response_model=Dict[str, Any],
    dependencies=[Depends(require_role(["owner", "admin"]))],
)
def update_transaction(
    trx_id: str,
    body: TransactionUpdate,
    current_user: UserInDB = Depends(get_current_user),
):
    """Edit header transaksi (jika belum locked)."""
    supabase = get_supabase()

    # Cek lock
    trx_resp = (
        supabase.table("transactions")
        .select("is_locked, tenant_id")
        .eq("id", trx_id)
        .eq("tenant_id", current_user.tenant_id)
        .single()
        .execute()
    )
    trx = getattr(trx_resp, "data", None)
    if not trx:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaksi tidak ditemukan")
    if trx.get("is_locked"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Transaksi terkunci")

    update_data = {k: v for k, v in body.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tidak ada data yang diupdate")

    resp = (
        supabase.table("transactions")
        .update(update_data)
        .eq("id", trx_id)
        .eq("tenant_id", current_user.tenant_id)
        .execute()
    )
    data = getattr(resp, "data", None) or []
    return {"success": True, "data": data[0] if data else {}}


# ─── DELETE /transactions/{id} ────────────────────────────────────────────────

@router.delete(
    "/{trx_id}",
    response_model=Dict[str, Any],
    dependencies=[Depends(require_role(["owner"]))],
)
def delete_transaction(
    trx_id: str,
    current_user: UserInDB = Depends(get_current_user),
):
    """Soft delete: set status = voided. Hanya owner."""
    supabase = get_supabase()

    trx_resp = (
        supabase.table("transactions")
        .select("is_locked, tenant_id")
        .eq("id", trx_id)
        .eq("tenant_id", current_user.tenant_id)
        .single()
        .execute()
    )
    trx = getattr(trx_resp, "data", None)
    if not trx:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaksi tidak ditemukan")
    if trx.get("is_locked"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Transaksi terkunci, tidak bisa dihapus")

    supabase.table("transactions").update({"status": "voided"}).eq(
        "id", trx_id
    ).eq("tenant_id", current_user.tenant_id).execute()

    return {"success": True, "message": "Transaksi dibatalkan"}
