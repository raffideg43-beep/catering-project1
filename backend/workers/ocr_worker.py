"""
backend/workers/ocr_worker.py
RQ Worker untuk async OCR nota foto — Modul 7

PENTING:
- Fungsi ini SYNC (bukan async) — RQ tidak support async native
- Dipanggil oleh rq worker process, bukan FastAPI
- Semua service dipanggil secara sync

Jalankan worker:
  rq worker ocr --url redis://localhost:6379
"""

import logging
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional

from redis import Redis
from rq import Queue, Retry

from core.config import settings
from core.database import get_supabase
from services.alias_service import AliasService
from services.notification_service import NotificationService
from services.ocr_service import OCRService
from services.validation_service import ValidationService

logger = logging.getLogger(__name__)

# ─── Redis + RQ setup ─────────────────────────────────────────────────────────

redis_conn = Redis.from_url(settings.redis_url)
ocr_queue = Queue("ocr", connection=redis_conn, default_timeout=120)


# ─── Helper: konversi nilai ke Decimal aman ───────────────────────────────────

def _to_decimal(val: Any, precision: str = "0.01") -> Decimal:
    try:
        return Decimal(str(val or 0)).quantize(Decimal(precision))
    except InvalidOperation:
        return Decimal("0")


def _to_decimal3(val: Any) -> Decimal:
    return _to_decimal(val, "0.001")


# ─── Fungsi utama job ─────────────────────────────────────────────────────────

def process_ocr_job(
    trx_id: str,
    photo_url: str,
    tenant_id: str,
    telegram_id: int,
) -> None:
    """
    RQ job entry-point.
    Alur: download foto → OCR → update DB → alias → insert items
          → validate → notif Telegram.
    """
    logger.info(f"OCR job start: trx={trx_id}, tenant={tenant_id}")

    supabase = get_supabase()
    bot_token = settings.telegram_bot_token or ""

    ocr_svc = OCRService()
    alias_svc = AliasService()
    val_svc = ValidationService()
    notif_svc = NotificationService()

    def _fail(reason: str) -> None:
        """Update status transaksi ke failed dan kirim notif gagal."""
        logger.error(f"OCR job failed [{trx_id}]: {reason}")
        try:
            supabase.table("transactions").update(
                {"status": "failed", "notes": reason}
            ).eq("id", trx_id).execute()
        except Exception as e:
            logger.error(f"Failed to update status: {e}")
        try:
            notif_svc._send_failed(telegram_id, bot_token)
        except Exception as e:
            logger.error(f"Failed to send notif: {e}")

    # ─── 1. Jalankan OCR via Gemini ──────────────────────────────────────────
    ocr_result: Optional[Dict] = ocr_svc.extract_from_url(photo_url)
    if ocr_result is None:
        _fail("OCR gagal — foto tidak dapat dibaca")
        return

    # ─── 2. Update header transaksi dari hasil OCR ───────────────────────────
    total_ocr = _to_decimal(ocr_result.get("total") or ocr_result.get("subtotal_nota", 0))
    ppn_amount = _to_decimal(ocr_result.get("ppn_amount", 0))
    subtotal_ocr = _to_decimal(ocr_result.get("subtotal_nota", 0)) or total_ocr
    diskon = _to_decimal(ocr_result.get("diskon", 0))

    trx_update = {
        "nama_toko": ocr_result.get("nama_toko"),
        "ref_number": ocr_result.get("no_nota"),
        "date": ocr_result.get("tanggal") or date.today().isoformat(),
        "subtotal": str(subtotal_ocr),
        "ppn_amount": str(ppn_amount),
        "pph22_amount": "0.00",          # PPh22 dihitung saat generate laporan
        "discount": str(diskon),
        "total": str(total_ocr),
        "payment_method": ocr_result.get("payment_method"),
        "payment_status": ocr_result.get("payment_status"),
        "due_date": ocr_result.get("due_date"),
        "ocr_confidence": ocr_result.get("ocr_confidence", 0.0),
        "is_pkp": ocr_result.get("is_pkp", False),
        "status": "processing",          # masih processing, items belum di-insert
    }

    try:
        supabase.table("transactions").update(trx_update).eq("id", trx_id).execute()
    except Exception as e:
        _fail(f"Update header transaksi gagal: {e}")
        return

    # ─── 3. Resolusi alias + insert transaction_items ─────────────────────────
    items_ocr = ocr_result.get("items") or []
    total_sum = Decimal("0")

    for item in items_ocr:
        nama_asli: str = item.get("nama_item", "Unknown")
        qty = _to_decimal3(item.get("qty", 1))
        satuan: str = item.get("satuan", "pcs")
        harga = _to_decimal(item.get("harga_satuan", 0))
        sub = _to_decimal(item.get("subtotal", 0))
        has_ppn: bool = bool(item.get("has_ppn", False))
        kategori: Optional[str] = item.get("kategori")

        # Validasi: hitung subtotal dari harga×qty jika tidak ada
        if sub == 0 and harga > 0 and qty > 0:
            sub = (harga * qty).quantize(Decimal("0.01"))

        # Hitung harga_satuan dari subtotal/qty jika tidak ada
        if harga == 0 and sub > 0 and qty > 0:
            harga = (sub / qty).quantize(Decimal("0.01"))

        total_sum += sub

        # Resolve alias → product_id
        alias_result = alias_svc.resolve(nama_asli, tenant_id, supabase)
        product_id = alias_result.get("product_id")
        product_name = alias_result.get("product_name") or nama_asli
        needs_confirm = alias_result.get("needs_confirmation", False)

        item_data = {
            "transaction_id": trx_id,
            "tenant_id": tenant_id,
            "product_id": product_id,
            "product_name": product_name,
            "qty": str(qty),
            "unit": satuan,
            "price": str(harga),
            "hpp_snapshot": str(harga),
            "has_ppn": has_ppn,
            "subtotal": str(sub),
            "needs_confirmation": needs_confirm,
        }

        try:
            supabase.table("transaction_items").insert(item_data).execute()
        except Exception as e:
            logger.warning(f"Item insert gagal '{nama_asli}': {e}")

    # ─── 4. Update total dari sum items jika berbeda dari OCR > Rp 100 ────────
    if total_sum > 0:
        diff = abs(total_sum - total_ocr)
        if diff > Decimal("100"):
            logger.info(f"Total dikoreksi: items={total_sum}, ocr={total_ocr}")
            # Simpan keduanya: total = dari nota (aktual), untuk validasi nanti

    # ─── 5. Validasi nota ─────────────────────────────────────────────────────
    try:
        val_svc.validate(trx_id, tenant_id, supabase)
    except Exception as e:
        logger.warning(f"Validasi gagal (non-fatal): {e}")

    # ─── 6. Pindahkan status ke pending_confirm ───────────────────────────────
    try:
        supabase.table("transactions").update({"status": "pending_confirm"}).eq(
            "id", trx_id
        ).execute()
    except Exception as e:
        logger.error(f"Status update pending_confirm gagal: {e}")

    # ─── 7. Kirim notif ke Telegram ───────────────────────────────────────────
    notif_svc.send_ocr_result(
        trx_id=trx_id,
        telegram_id=telegram_id,
        bot_token=bot_token,
        supabase=supabase,
    )

    logger.info(f"OCR job selesai: trx={trx_id}, {len(items_ocr)} items")


# ─── Helper: enqueue job dari router ─────────────────────────────────────────

def enqueue_ocr_job(
    trx_id: str,
    photo_url: str,
    tenant_id: str,
    telegram_id: int,
) -> str:
    """
    Panggil ini dari FastAPI router untuk push job ke Redis queue.
    Return job ID.
    """
    job = ocr_queue.enqueue(
        process_ocr_job,
        trx_id,
        photo_url,
        tenant_id,
        telegram_id,
        retry=Retry(max=3, interval=[10, 30, 60]),
    )
    logger.info(f"OCR job enqueued: job_id={job.id}, trx={trx_id}")
    return job.id
