"""
bot/handlers/nota_handler.py
Handler untuk foto nota: upload → backend → OCR async — Modul 7

Alur:
  User kirim foto → download dari Telegram → POST /transactions/from-photo
  Backend OCR selesai → worker kirim notif balik ke user
  User klik Konfirmasi/Edit/Batalkan → callback handler
"""

import logging
from io import BytesIO

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

from core.config import settings
from keyboards.main_menu import get_main_menu
from utils.api_client import get_api_client
from utils.formatter import format_error
from utils.session import get_token, get_role, is_authenticated

logger = logging.getLogger(__name__)

# Role yang boleh input transaksi
CAN_INPUT_ROLES = {"owner", "admin", "kasir"}


def _can_input(context: ContextTypes.DEFAULT_TYPE) -> bool:
    role = get_role(context)
    return role in CAN_INPUT_ROLES


# ─── Handler: user kirim foto ─────────────────────────────────────────────────

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Terima foto dari user:
      1. Cek auth + role
      2. Download foto (ukuran terbesar)
      3. POST ke /transactions/from-photo (multipart)
      4. Reply dengan status pending
    """
    if not update.message or not update.message.photo:
        return

    # ─── Cek auth ────────────────────────────────────────────────────
    if not is_authenticated(context):
        await update.message.reply_text(
            "❌ Silakan /start dulu untuk login.",
            reply_markup=get_main_menu(),
        )
        return

    if not _can_input(context):
        await update.message.reply_text(
            "❌ Hanya owner, admin, dan kasir yang bisa upload nota."
        )
        return

    # ─── Download foto — ambil ukuran terbesar ────────────────────────
    photo = update.message.photo[-1]   # index -1 = resolusi terbesar
    await update.message.reply_text("⏳ Mengirim foto...")

    try:
        photo_file = await photo.get_file()
        photo_bytes = await photo_file.download_as_bytearray()
    except Exception as e:
        logger.error(f"Download foto gagal: {e}")
        await update.message.reply_text(
            format_error(f"Gagal mengambil foto: {e}")
        )
        return

    # ─── Upload ke backend via multipart ─────────────────────────────
    token = get_token(context)
    api = get_api_client(settings.backend_url)  # type: ignore[attr-defined]

    telegram_id = update.effective_user.id if update.effective_user else 0
    filename = f"{telegram_id}_{photo.file_unique_id}.jpg"

    try:
        resp = await api.post(
            "/transactions/from-photo",
            token=token,
            files={
                "file": (filename, bytes(photo_bytes), "image/jpeg"),
            },
        )
    except Exception as e:
        logger.error(f"Upload foto error: {e}")
        await update.message.reply_text(
            "❌ Gagal mengirim foto ke server.\n\n"
            "Coba lagi atau gunakan /belanja untuk input manual.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✏️ Input Manual", callback_data="belanja_manual")],
            ]),
        )
        return

    if not resp.get("success"):
        await update.message.reply_text(
            format_error(resp.get("detail", "Upload gagal"))
        )
        return

    data = resp.get("data", {})
    trx_id = data.get("transaction_id", "")

    # Simpan di context untuk penggunaan callback selanjutnya
    context.user_data["last_trx_id"] = trx_id

    await update.message.reply_text(
        "📸 *Foto diterima\\!*\n\n"
        "⏳ Sedang membaca nota\\.\\.\\.\n"
        "Kami akan kabari setelah selesai\\.",
        parse_mode="MarkdownV2",
    )


# ─── Callback: konfirmasi nota ────────────────────────────────────────────────

async def confirm_nota(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Callback data: confirm_{trx_id}
    POST /transactions/{trx_id}/confirm
    """
    query = update.callback_query
    if not query:
        return
    await query.answer()

    trx_id = query.data.replace("confirm_", "")
    token = get_token(context)
    api = get_api_client(settings.backend_url)  # type: ignore[attr-defined]

    try:
        resp = await api.post(f"/transactions/{trx_id}/confirm", token=token)
    except Exception as e:
        await query.edit_message_text(format_error(f"Gagal konfirmasi: {e}"))
        return

    if not resp.get("success"):
        await query.edit_message_text(
            format_error(resp.get("detail", "Konfirmasi gagal"))
        )
        return

    warnings = resp.get("stok_warnings", [])
    warn_text = ""
    if warnings:
        warn_text = "\n\n⚠️ " + "\n⚠️ ".join(warnings[:3])

    await query.edit_message_text(
        f"✅ *Nota dikonfirmasi\\!*\n\n"
        f"Stok \\& arus kas sudah diupdate\\.{_esc(warn_text)}",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📊 Lihat Ringkasan", callback_data="show_summary"),
                InlineKeyboardButton("← Menu Utama", callback_data="main_menu_callback"),
            ]
        ]),
        parse_mode="MarkdownV2",
    )


# ─── Callback: edit nota ──────────────────────────────────────────────────────

async def edit_nota(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Callback data: edit_{trx_id}
    Tampilkan daftar items untuk dipilih user yang ingin diedit.
    """
    query = update.callback_query
    if not query:
        return
    await query.answer()

    trx_id = query.data.replace("edit_", "")
    token = get_token(context)
    api = get_api_client(settings.backend_url)  # type: ignore[attr-defined]

    try:
        resp = await api.get(f"/transactions/{trx_id}", token=token)
    except Exception as e:
        await query.edit_message_text(format_error(f"Tidak bisa load: {e}"))
        return

    trx = resp.get("data", {})
    items = trx.get("items", [])
    nama_toko = trx.get("nama_toko") or "Nota"

    # Simpan context untuk edit item selanjutnya
    context.user_data["editing_trx_id"] = trx_id
    context.user_data["editing_items"] = items

    buttons = []
    for idx, item in enumerate(items):
        qty = float(item.get("qty", 0))
        sat = item.get("unit", "pcs")
        harga_raw = item.get("price", 0)
        harga = f"Rp {int(harga_raw):,}".replace(",", ".")
        nama = item.get("product_name", "?")[:20]
        conf = " ⚠️" if item.get("needs_confirmation") else ""
        buttons.append([
            InlineKeyboardButton(
                f"✏️ {nama}{conf}: {qty}{sat} {harga}",
                callback_data=f"edit_item_{trx_id}_{idx}",
            )
        ])

    buttons.append([InlineKeyboardButton("← Kembali", callback_data=f"back_nota_{trx_id}")])

    await query.edit_message_text(
        f"✏️ *Edit Nota — {_esc(nama_toko)}*\n\n"
        f"Pilih item yang ingin diedit \\({len(items)} item\\):",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="MarkdownV2",
    )


# ─── Callback: batalkan nota ──────────────────────────────────────────────────

async def cancel_nota(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Callback data: cancel_{trx_id}
    DELETE /transactions/{trx_id} (soft delete — status=voided)
    """
    query = update.callback_query
    if not query:
        return
    await query.answer()

    trx_id = query.data.replace("cancel_", "")
    token = get_token(context)
    api = get_api_client(settings.backend_url)  # type: ignore[attr-defined]

    try:
        await api.delete(f"/transactions/{trx_id}", token=token)
    except Exception as e:
        await query.edit_message_text(format_error(f"Gagal batalkan: {e}"))
        return

    await query.edit_message_text(
        "❌ Nota dibatalkan\\.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("← Menu Utama", callback_data="main_menu_callback")]
        ]),
        parse_mode="MarkdownV2",
    )


# ─── Callback: edit item spesifik ─────────────────────────────────────────────

async def edit_item(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Callback data: edit_item_{trx_id}_{item_idx}
    Tampilkan detail item dan instruksi edit.
    """
    query = update.callback_query
    if not query:
        return
    await query.answer()

    parts = query.data.split("_")
    # format: edit_item_{trx_id}_{idx} — trx_id bisa punya dash
    # edit_item_ prefix = 10 chars, idx = parts[-1]
    try:
        item_idx = int(parts[-1])
        trx_id = "_".join(parts[2:-1])
    except (ValueError, IndexError):
        await query.edit_message_text(format_error("Data tidak valid"))
        return

    items = context.user_data.get("editing_items", [])
    if item_idx >= len(items):
        await query.edit_message_text(format_error("Item tidak ditemukan"))
        return

    item = items[item_idx]
    nama = item.get("product_name", "?")
    qty = float(item.get("qty", 0))
    sat = item.get("unit", "pcs")
    harga = item.get("price", 0)
    conf_note = ""
    if item.get("needs_confirmation"):
        conf_note = "\n⚠️ _Nama item ini tidak cocok di database produk_"

    context.user_data["editing_item_idx"] = item_idx
    context.user_data["editing_item_id"] = item.get("id")

    await query.edit_message_text(
        f"✏️ *Edit: {_esc(nama)}*{conf_note}\n\n"
        f"Qty saat ini: {qty} {_esc(sat)}\n"
        f"Harga saat ini: Rp {int(harga):,}\n\n".replace(",", ".") +
        "Ketik: `qty\\_baru harga\\_baru`\n"
        "Contoh: `10 12500`\n\n"
        "Atau ketik /skip untuk kembali tanpa ubah\\.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("← Kembali", callback_data=f"edit_{trx_id}")]
        ]),
        parse_mode="MarkdownV2",
    )


def _esc(text: str) -> str:
    import re
    if not text:
        return ""
    return re.sub(r"([_*\[\]()~`>#+\-=|{}.!\\])", r"\\\1", str(text))
