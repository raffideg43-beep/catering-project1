"""
backend/services/notification_service.py
Kirim notifikasi Telegram dari worker — Modul 7

Menggunakan Telegram Bot API langsung (HTTP POST),
bukan via python-telegram-bot — karena dipanggil dari RQ worker sync.
"""

import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

TG_API = "https://api.telegram.org/bot{token}/sendMessage"
TG_MAX_TEXT = 4096  # batas karakter pesan Telegram


def _fmt_rp(amount) -> str:
    """Format angka ke Rp 12.000."""
    try:
        v = int(Decimal(str(amount)))
        return f"Rp {v:,}".replace(",", ".")
    except Exception:
        return f"Rp {amount}"


def _build_inline_keyboard(trx_id: str) -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "✅ Konfirmasi", "callback_data": f"confirm_{trx_id}"},
                {"text": "✏️ Edit", "callback_data": f"edit_{trx_id}"},
                {"text": "❌ Batalkan", "callback_data": f"cancel_{trx_id}"},
            ]
        ]
    }


def _build_retry_keyboard() -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "🔄 Kirim Ulang", "callback_data": "retry_photo"},
                {"text": "✏️ Input Manual", "callback_data": "belanja_manual"},
            ]
        ]
    }


class NotificationService:
    """Sync — dipanggil dari RQ worker."""

    def send_ocr_result(
        self,
        trx_id: str,
        telegram_id: int,
        bot_token: str,
        supabase,
    ) -> bool:
        """
        Ambil data transaksi dari DB, format pesan, kirim ke Telegram user.
        Return True jika berhasil.
        """
        # ─── Ambil data transaksi ───────────────────────────────────
        trx_resp = (
            supabase.table("transactions")
            .select("*")
            .eq("id", trx_id)
            .single()
            .execute()
        )
        trx: Optional[Dict] = getattr(trx_resp, "data", None)
        if not trx:
            logger.error(f"notif: transaksi {trx_id} tidak ditemukan")
            return False

        items_resp = (
            supabase.table("transaction_items")
            .select("*")
            .eq("transaction_id", trx_id)
            .execute()
        )
        items: List[dict] = getattr(items_resp, "data", None) or []

        # ─── Cek apakah OCR berhasil ────────────────────────────────
        if trx.get("status") == "failed":
            return self._send_failed(telegram_id, bot_token)

        # ─── Ambil flags validasi ───────────────────────────────────
        val_resp = (
            supabase.table("nota_validations")
            .select("flags, result")
            .eq("transaction_id", trx_id)
            .limit(1)
            .execute()
        )
        val_rows = getattr(val_resp, "data", None) or []
        flags_data = (val_rows[0].get("flags", {}) if val_rows else {}) or {}
        warnings: List[str] = flags_data.get("warnings", [])

        # ─── Bangun teks pesan ──────────────────────────────────────
        nama_toko = trx.get("nama_toko") or "Tidak diketahui"
        tanggal = trx.get("date", "")
        no_nota = trx.get("ref_number") or "-"
        total = _fmt_rp(trx.get("total", 0))


        lines = [
            "✅ *Nota berhasil dibaca\\!*",
            "",
            f"📅 {tanggal}  |  🏪 {_esc(nama_toko)}",
            f"🧾 No: {_esc(no_nota)}  |  💰 Total: {_esc(total)}",
        ]



        lines += ["", f"📦 *{len(items)} item:*"]

        # Tampilkan maks 8 item agar pesan tidak terlalu panjang
        for item in items[:8]:
            qty = float(item.get("qty", 0))
            sat = _esc(item.get("unit", "pcs"))
            harga = _fmt_rp(item.get("price", 0))
            sub = _fmt_rp(item.get("subtotal", 0))
            nama = _esc(item.get("product_name", "?"))
            conf = ""
            if item.get("needs_confirmation"):
                conf = " ⚠️"
            lines.append(f"• {nama}{conf}: {qty}{sat} × {_esc(harga)} \\= {_esc(sub)}")

        if len(items) > 8:
            lines.append(f"_\\.\\.\\. {len(items)-8} item lainnya_")

        if warnings:
            lines += ["", "⚠️ *Perhatian:*"]
            for w in warnings[:3]:
                lines.append(f"• {_esc(w)}")

        needs_confirm_count = sum(1 for i in items if i.get("needs_confirmation"))
        if needs_confirm_count:
            lines.append(f"\n⚠️ {needs_confirm_count} item nama tidak cocok di produk — perlu konfirmasi manual")

        text = "\n".join(lines)
        # Potong jika terlalu panjang
        if len(text) > TG_MAX_TEXT - 50:
            text = text[:TG_MAX_TEXT - 50] + "\n_\\[pesan dipotong\\]_"

        return self._send(
            telegram_id=telegram_id,
            bot_token=bot_token,
            text=text,
            reply_markup=_build_inline_keyboard(trx_id),
        )

    def _send_failed(self, telegram_id: int, bot_token: str) -> bool:
        text = (
            "❌ *Nota gagal dibaca\\.*\n\n"
            "Kemungkinan foto buram atau terpotong\\.\n"
            "Coba foto ulang dengan pencahayaan lebih baik\\."
        )
        return self._send(
            telegram_id=telegram_id,
            bot_token=bot_token,
            text=text,
            reply_markup=_build_retry_keyboard(),
        )

    def _send(
        self,
        telegram_id: int,
        bot_token: str,
        text: str,
        reply_markup: Optional[dict] = None,
    ) -> bool:
        url = TG_API.format(token=bot_token)
        payload: Dict[str, Any] = {
            "chat_id": telegram_id,
            "text": text,
            "parse_mode": "MarkdownV2",
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        try:
            with httpx.Client(timeout=15) as client:
                resp = client.post(url, json=payload)
                resp.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"Telegram notif gagal ke {telegram_id}: {e}")
            return False


def _esc(text: str) -> str:
    """Escape MarkdownV2 chars."""
    import re
    if not isinstance(text, str):
        text = str(text)
    return re.sub(r"([_*\[\]()~`>#+\-=|{}.!\\])", r"\\\1", text)


notification_service = NotificationService()
