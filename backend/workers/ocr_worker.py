"""
backend/workers/ocr_worker.py
OCR Worker untuk nota foto — Modul 7

Dijalankan via FastAPI BackgroundTasks (non-blocking, thread pool).
Tidak menggunakan RQ/Redis karena rq tidak kompatibel Windows (fork()).

Untuk production Linux, fungsi process_ocr_job bisa dijalankan via RQ:
  from rq import Queue
  Queue("ocr", connection=redis_conn).enqueue(process_ocr_job, ...)

Jalankan: sudah terintegrasi di FastAPI, tidak perlu daemon terpisah.
"""

import logging
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional

from core.config import settings
from core.database import get_supabase
from services.alias_service import AliasService
from services.notification_service import NotificationService
from services.ocr_service import OCRService
from services.validation_service import ValidationService

logger = logging.getLogger(__name__)


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
    batch_id: Optional[str] = None,
) -> None:
    """
    RQ job entry-point.
    Alur: download foto → OCR → update DB → alias → insert items
          → validate → notif Telegram.
    Jika batch_id ada, update photo_batches counter dan kirim notif batch jika complete.
    """
    logger.info(f"OCR job start: trx={trx_id}, tenant={tenant_id}, batch={batch_id}")

    supabase = get_supabase()
    bot_token = settings.telegram_bot_token or ""

    ocr_svc = OCRService()
    alias_svc = AliasService()
    val_svc = ValidationService()
    notif_svc = NotificationService()

    success = False

    def _fail(reason: str) -> None:
        """Update status transaksi ke failed dan kirim notif gagal."""
        logger.error(f"OCR job failed [{trx_id}]: {reason}")
        try:
            supabase.table("transactions").update(
                {"status": "failed", "notes": reason}
            ).eq("id", trx_id).execute()
        except Exception as e:
            logger.error(f"Failed to update status: {e}")
        if not batch_id:
            try:
                notif_svc._send_failed(telegram_id, bot_token)
            except Exception as e:
                logger.error(f"Failed to send notif: {e}")

    # ─── 1. Jalankan OCR via Gemini ──────────────────────────────────────────
    ocr_result: Optional[Dict] = ocr_svc.extract_from_url(photo_url)
    if ocr_result is None:
        _fail("OCR gagal — foto tidak dapat dibaca")
        _update_batch_counter(batch_id, trx_id, tenant_id, telegram_id, bot_token, supabase, success=False, error="OCR gagal")
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
        "pph22_amount": "0.00",
        "discount": str(diskon),
        "total": str(total_ocr),
        "payment_method": ocr_result.get("payment_method"),
        "payment_status": ocr_result.get("payment_status"),
        "ocr_confidence": ocr_result.get("ocr_confidence", 0.0),
        "is_pkp": ocr_result.get("is_pkp", False),
        "status": "processing",
    }

    try:
        supabase.table("transactions").update(trx_update).eq("id", trx_id).execute()
    except Exception as e:
        _fail(f"Update header transaksi gagal: {e}")
        _update_batch_counter(batch_id, trx_id, tenant_id, telegram_id, bot_token, supabase, success=False, error=str(e))
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

        if sub == 0 and harga > 0 and qty > 0:
            sub = (harga * qty).quantize(Decimal("0.01"))
        if harga == 0 and sub > 0 and qty > 0:
            harga = (sub / qty).quantize(Decimal("0.01"))

        total_sum += sub

        alias_result = alias_svc.resolve(nama_asli, tenant_id, supabase)
        product_id = alias_result.get("product_id")
        product_name = alias_result.get("product_name") or nama_asli
        needs_confirm = alias_result.get("needs_confirmation", False)

        # ─── Konversi qty dari satuan nota ke base unit ─────────────
        try:
            from utils.unit_converter import get_base_unit as _get_base_unit
            _, nota_factor = _get_base_unit(satuan)
            qty_base = _to_decimal3(float(qty) * nota_factor)
        except Exception:
            qty_base = qty

        item_data = {
            "transaction_id": trx_id,
            "tenant_id": tenant_id,
            "product_id": product_id,
            "product_name": product_name,
            "qty": str(qty_base),
            "unit": satuan,
            "price": str(harga),
            "harga_snapshot": str(harga),
            "has_ppn": has_ppn,
            "subtotal": str(sub),
        }

        try:
            supabase.table("transaction_items").insert(item_data).execute()
        except Exception as e:
            logger.warning(f"Item insert gagal '{nama_asli}': {e}")

    # ─── 4. Validasi nota ─────────────────────────────────────────────────────
    try:
        val_svc.validate(trx_id, tenant_id, supabase)
    except Exception as e:
        logger.warning(f"Validasi gagal (non-fatal): {e}")

    # ─── 5. Update status ke pending_confirm ──────────────────────────────────
    try:
        supabase.table("transactions").update({"status": "pending_confirm"}).eq(
            "id", trx_id
        ).execute()
    except Exception as e:
        logger.error(f"Status update pending_confirm gagal: {e}")

    success = True

    # ─── 6. Notif single foto (jika bukan batch) ──────────────────────────────
    if not batch_id:
        notif_svc.send_ocr_result(
            trx_id=trx_id,
            telegram_id=telegram_id,
            bot_token=bot_token,
            supabase=supabase,
        )

    # ─── 7. Update batch counter (jika batch) ─────────────────────────────────
    _update_batch_counter(batch_id, trx_id, tenant_id, telegram_id, bot_token, supabase, success=success)

    logger.info(f"OCR job selesai: trx={trx_id}, {len(items_ocr)} items")


# ─── Helper: update batch counter ────────────────────────────────────────────

def _update_batch_counter(
    batch_id: Optional[str],
    trx_id: str,
    tenant_id: str,
    telegram_id: int,
    bot_token: str,
    supabase,
    success: bool = True,
    error: Optional[str] = None,
) -> None:
    """Update photo_batches counter dan kirim notif jika batch complete."""
    if not batch_id:
        return

    try:
        # Ambil batch saat ini
        batch_resp = (
            supabase.table("photo_batches")
            .select("*")
            .eq("id", batch_id)
            .eq("tenant_id", tenant_id)
            .single()
            .execute()
        )
        batch = getattr(batch_resp, "data", None)
        if not batch:
            logger.warning(f"Batch {batch_id} tidak ditemukan di database. Pastikan record photo_batches sudah terbuat.")
            return

        # Update counter
        processed_photos = batch.get("processed_photos", 0)
        total = batch.get("total_photos", 1)

        if success:
            processed_photos += 1

        is_complete = processed_photos >= total
        batch_status = "done" if is_complete else "processing"

        supabase.table("photo_batches").update({
            "processed_photos": processed_photos,
            "status": batch_status,
        }).eq("id", batch_id).execute()

        # Kirim notif batch jika sudah complete
        if is_complete:
            _send_batch_complete(
                batch_id=batch_id,
                telegram_id=telegram_id,
                bot_token=bot_token,
                supabase=supabase,
                total=total,
                processed=processed_photos,
                failed=total - processed_photos,
                photos=[], # Database lacks 'photos' column
            )

    except Exception as e:
        logger.error(f"Update batch counter gagal [{batch_id}]: {e}")


# ─── Helper: kirim notif batch complete ke Telegram ──────────────────────────

def _fmt_rp_worker(amount) -> str:
    try:
        v = int(Decimal(str(amount or 0)))
        return f"Rp {v:,}".replace(",", ".")
    except Exception:
        return f"Rp {amount}"


def _esc_worker(text: str) -> str:
    import re
    if not isinstance(text, str):
        text = str(text)
    return re.sub(r"([_*\[\]()~`>#+\-=|{}.!\\])", r"\\\1", text)


def _send_batch_complete(
    batch_id: str,
    telegram_id: int,
    bot_token: str,
    supabase,
    total: int,
    processed: int,
    failed: int,
    photos: list,
) -> None:
    """Kirim ringkasan batch ke Telegram user via HTTP langsung."""
    import httpx

    # Ambil data transaksi yang berhasil
    trx_ids = [p["trx_id"] for p in photos if p.get("trx_id") and p.get("status") == "done"]
    trx_map: Dict = {}
    if trx_ids:
        trx_resp = (
            supabase.table("transactions")
            .select("id, nama_toko, total, status")
            .in_("id", trx_ids)
            .execute()
        )
        trx_map = {t["id"]: t for t in (getattr(trx_resp, "data", None) or [])}

    # ─── Buat pesan ───────────────────────────────────────────────────
    lines = []
    inline_keyboard = []

    if failed == 0:
        lines.append(f"✅ *{total} nota selesai diproses\\!*\n")
        lines.append("Semua data berhasil diekstrak dan siap dikonfirmasi\\.")
    elif processed > 0:
        lines.append(f"⚠️ *{processed} berhasil, {failed} gagal\\.*\n")
    else:
        lines.append(f"❌ *Semua {total} nota gagal dibaca\\.*\n")
        lines.append("Kemungkinan foto buram atau terpotong\\.")

    # Tombol konfirmasi semua / batal semua
    if processed > 0:
        inline_keyboard.append([
            {"text": f"✅ Konfirmasi Semua ({processed})",
             "callback_data": f"konfirmasi_semua_{batch_id}"},
            {"text": "❌ Batal Semua",
             "callback_data": f"batal_semua_{batch_id}"},
        ])

    if failed > 0:
        inline_keyboard.append([{
            "text": "🔄 Kirim Ulang Foto yang Gagal",
            "callback_data": f"kirim_ulang_{batch_id}",
        }])

    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:4000] + "\n_\\[pesan dipotong\\]_"

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": telegram_id,
        "text": text,
        "parse_mode": "MarkdownV2",
        "reply_markup": {"inline_keyboard": inline_keyboard} if inline_keyboard else None,
    }
    if payload["reply_markup"] is None:
        del payload["reply_markup"]

    try:
        with httpx.Client(timeout=15) as client:
            client.post(url, json=payload)
    except Exception as e:
        logger.error(f"Batch complete notif gagal: {e}")


# ─── Helper untuk FastAPI BackgroundTasks ─────────────────────────────────────

def run_ocr_in_background(
    trx_id: str,
    photo_url: str,
    tenant_id: str,
    telegram_id: int,
    batch_id: Optional[str] = None,
) -> None:
    """
    Entry-point untuk FastAPI BackgroundTasks.
    Dipanggil di thread pool (non-blocking terhadap request).
    """
    try:
        process_ocr_job(
            trx_id=trx_id,
            photo_url=photo_url,
            tenant_id=tenant_id,
            telegram_id=telegram_id,
            batch_id=batch_id,
        )
    except Exception as e:
        logger.error(f"Background OCR error [{trx_id}]: {e}")

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
            "harga_snapshot": str(harga),
            "has_ppn": has_ppn,
            "subtotal": str(sub),
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


# ─── Helper untuk FastAPI BackgroundTasks ─────────────────────────────────────

def run_ocr_in_background(
    trx_id: str,
    photo_url: str,
    tenant_id: str,
    telegram_id: int,
    batch_id: Optional[str] = None,
) -> None:
    """
    Entry-point untuk FastAPI BackgroundTasks.
    Dipanggil di thread pool (non-blocking terhadap request).
    Langsung memanggil process_ocr_job sync.
    """
    try:
        process_ocr_job(
            trx_id=trx_id,
            photo_url=photo_url,
            tenant_id=tenant_id,
            telegram_id=telegram_id,
            batch_id=batch_id,
        )
    except Exception as e:
        logger.error(f"Background OCR error [{trx_id}]: {e}")
