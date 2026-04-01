"""
bot/handlers/menu_handler.py
ConversationHandler untuk /menu — input menu mingguan MBG
Modul 6 | MASTER_PLAN v1.7

States:
  SHOW_WEEK        = 0  → tampilkan grid minggu, user klik hari
  WAITING_INPUT    = 1  → user diminta ketik nama menu
  VALIDATING_MENU  = 2  → user sudah ketik, bot validasi ke backend
  CONFIRM_NO_BOM   = 3  → user pilih simpan (ada/tanpa BOM)
  INPUT_BOM_INLINE = 4  → user input bahan BOM baris per baris
"""

import logging
import re
from datetime import date, timedelta
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from core.config import settings
from keyboards.main_menu import get_main_menu
from keyboards.menu_keyboard import (
    get_bom_cancel_keyboard,
    get_bom_confirm_keyboard,
    get_cancel_keyboard,
    get_day_action_keyboard,
    get_new_product_keyboard,
    get_no_bom_keyboard,
    get_week_keyboard,
)
from utils.api_client import get_api_client
from utils.formatter import format_error, format_success
from utils.session import get_token, is_authenticated, get_role

logger = logging.getLogger(__name__)

# ─── States ───────────────────────────────────────────────────────────────────
SHOW_WEEK        = 0
WAITING_INPUT    = 1
VALIDATING_MENU  = 2
CONFIRM_NO_BOM   = 3
INPUT_BOM_INLINE = 4

# ─── Helpers ──────────────────────────────────────────────────────────────────

HARI_ID = {1: "Senin", 2: "Selasa", 3: "Rabu", 4: "Kamis", 5: "Jumat", 6: "Sabtu"}


def _esc(text: str) -> str:
    import re
    if not text: return ""
    return re.sub(r"([_*\[\]()~`>#+\-=|{}.!\\])", r"\\\1", str(text))


def _get_week_start(target: date) -> date:
    return target - timedelta(days=target.weekday())


def _format_week_text(week_data: list, week_start: str, week_end: str) -> str:
    """Format teks tampilan agenda minggu."""
    try:
        ws_date = date.fromisoformat(week_start)
        we_date = date.fromisoformat(week_end)
        periode = (
            f"{ws_date.day} {_bulan(ws_date.month)} — "
            f"{we_date.day} {_bulan(we_date.month)} {we_date.year}"
        )
    except Exception:
        periode = f"{week_start} — {week_end}"

    lines = ["📅 *MENU MINGGU INI*", f"Periode: {_esc(periode)}", ""]

    for entry in week_data:
        day = entry["day_name"]
        try:
            d = date.fromisoformat(entry["date"])
            tanggal = f"{d.day} {_bulan(d.month)}"
        except Exception:
            tanggal = entry["date"]

        if entry.get("is_filled") and entry.get("menu_name"):
            bom_icon = "✅" if entry.get("has_bom") else "⚠️"
            lines.append(_esc(f"{day:<7} {tanggal}: {entry['menu_name']} {bom_icon}"))
        elif day == "Sabtu":
            lines.append(_esc(f"{day:<7} {tanggal}: [opsional] ⬜"))
        else:
            lines.append(_esc(f"{day:<7} {tanggal}: [belum diisi] ⬜"))

    lines.append("")
    lines.append(_esc("✅ = BOM tersedia  |  ⚠️ = tanpa BOM"))
    return "\n".join(lines)


def _bulan(m: int) -> str:
    return ["Jan","Feb","Mar","Apr","Mei","Jun","Jul","Agu","Sep","Okt","Nov","Des"][m - 1]


async def _show_week(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    edit: bool = False,
    week_start: Optional[str] = None,
) -> int:
    """Ambil data minggu dari backend dan render tampilan."""
    token = get_token(context)
    api = get_api_client(settings.backend_url)  # type: ignore[attr-defined]

    params = {}
    if week_start:
        params["week_start"] = week_start

    try:
        resp = await api.get("/mbg/weekly-menus", token=token, params=params or None)
    except Exception as e:
        from utils.api_client import APIError
        if isinstance(e, APIError) and e.status_code in (401, 403): raise e
        msg = format_error(f"Tidak bisa load menu: {e}")
        if edit and update.callback_query:
            await update.callback_query.edit_message_text(msg)
        elif update.message:
            await update.message.reply_text(msg)
        return SHOW_WEEK

    week_data = resp.get("data", [])
    ws = resp.get("week_start", "")
    we = resp.get("week_end", "")

    # Simpan di context untuk reuse
    context.user_data["week_data"] = week_data
    context.user_data["week_start"] = ws

    text = _format_week_text(week_data, ws, we)
    kb = get_week_keyboard(week_data)

    if edit and update.callback_query:
        await update.callback_query.edit_message_text(
            text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN_V2
        )
    elif update.message:
        await update.message.reply_text(
            text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN_V2
        )

    return SHOW_WEEK


# ─── Entry point: /menu command ───────────────────────────────────────────────

async def menu_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handler /menu — cek auth lalu tampilkan grid minggu."""
    if not is_authenticated(context):
        if update.message:
            await update.message.reply_text(
                "❌ Silakan /start dulu untuk login.",
                reply_markup=get_main_menu(get_role(context) or ""),
            )
        elif update.callback_query:
            await update.callback_query.answer("❌ Silakan login dulu.", show_alert=True)
        return ConversationHandler.END

    user_role = get_role(context)
    if user_role not in ["owner", "admin"]:
        msg = "⛔ Akses Ditolak. Fitur ini hanya untuk Owner dan Admin."
        if update.message:
            await update.message.reply_text(msg)
        elif update.callback_query:
            await update.callback_query.answer(msg, show_alert=True)
        return ConversationHandler.END

    if update.callback_query:
        await update.callback_query.answer()
        return await _show_week(update, context, edit=True)

    return await _show_week(update, context)


# ─── SHOW_WEEK: user klik tombol hari ─────────────────────────────────────────

async def on_edit_day(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User klik salah satu hari — tampilkan aksi edit atau langsung minta input."""
    query = update.callback_query
    if not query:
        return SHOW_WEEK
    await query.answer()

    # Ekstrak tanggal dari callback_data "edit_day_YYYY-MM-DD"
    date_str = query.data.replace("edit_day_", "")
    context.user_data["editing_date"] = date_str

    # Cek apakah hari ini sudah terisi
    week_data: list = context.user_data.get("week_data", [])
    entry = next((e for e in week_data if e["date"] == date_str), None)

    if entry and entry.get("is_filled") and entry.get("menu_name"):
        # Hari sudah terisi → tampilkan pilihan Ganti/Hapus
        try:
            d = date.fromisoformat(date_str)
            label = f"{HARI_ID.get(d.weekday()+1, '')} {d.day} {_bulan(d.month)}"
        except Exception:
            label = date_str

        bom_note = ""
        if entry.get("has_bom"):
            bom_note = "\n✅ BOM tersedia"
        else:
            bom_note = "\n⚠️ Belum ada BOM — stok tidak terpotong otomatis"

        await query.edit_message_text(
            f"✏️ Menu *{_esc(label)}* saat ini:\n"
            f"*{_esc(entry['menu_name'])}*{_esc(bom_note)}\n\n"
            "Pilih aksi:",
            reply_markup=get_day_action_keyboard(date_str, entry["menu_name"]),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return SHOW_WEEK

    # Hari belum terisi → langsung minta input nama menu
    return await _ask_menu_input(query, context, date_str)


async def _ask_menu_input(query_or_update, context: ContextTypes.DEFAULT_TYPE, date_str: str) -> int:
    """Minta user ketik nama menu untuk hari tertentu."""
    try:
        d = date.fromisoformat(date_str)
        label = f"{HARI_ID.get(d.weekday()+1, '')} {d.day} {_bulan(d.month)}"
    except Exception:
        label = date_str

    text = (
        f"📝 Menu untuk *{_esc(label)}*:\n\n"
        "Ketik nama menu\\:"
    )
    if hasattr(query_or_update, "edit_message_text"):
        await query_or_update.edit_message_text(
            text,
            reply_markup=get_cancel_keyboard(),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
    else:
        await query_or_update.reply_text(
            text,
            reply_markup=get_cancel_keyboard(),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
    return WAITING_INPUT


async def on_change_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User klik 'Ganti Menu' dari tampilan hari terisi."""
    query = update.callback_query
    if not query:
        return SHOW_WEEK
    await query.answer()

    date_str = query.data.replace("change_menu_", "")
    context.user_data["editing_date"] = date_str
    return await _ask_menu_input(query, context, date_str)


async def on_delete_day(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User klik 'Hapus' untuk menghapus menu hari tertentu."""
    query = update.callback_query
    if not query:
        return SHOW_WEEK
    await query.answer()

    date_str = query.data.replace("delete_day_", "")
    token = get_token(context)
    api = get_api_client(settings.backend_url)  # type: ignore[attr-defined]

    try:
        await api.delete(f"/mbg/weekly-menus/{date_str}", token=token)
    except Exception as e:
        from utils.api_client import APIError
        if isinstance(e, APIError) and e.status_code in (401, 403): raise e
        await query.edit_message_text(format_error(f"Gagal hapus: {e}"))
        return SHOW_WEEK

    # Refresh tampilan minggu
    ws = context.user_data.get("week_start")
    return await _show_week(update, context, edit=True, week_start=ws)


async def on_back_to_week(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Kembali ke tampilan minggu tanpa perubahan."""
    query = update.callback_query
    if not query:
        return SHOW_WEEK
    await query.answer()
    ws = context.user_data.get("week_start")
    return await _show_week(update, context, edit=True, week_start=ws)


async def on_save_week(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User klik 'Simpan Semua' — tampilkan konfirmasi selesai."""
    query = update.callback_query
    if not query:
        return SHOW_WEEK
    await query.answer("✅ Menu minggu ini sudah tersimpan!", show_alert=True)
    ws = context.user_data.get("week_start")
    return await _show_week(update, context, edit=True, week_start=ws)


# ─── WAITING_INPUT: user ketik nama menu ──────────────────────────────────────

async def on_menu_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    User mengetik nama menu. Kirim ke /mbg/weekly-menus/validate.
    """
    if not update.message or not update.message.text:
        return WAITING_INPUT

    menu_name = update.message.text.strip()
    if len(menu_name) < 2:
        await update.message.reply_text(
            "⚠️ Nama menu terlalu pendek. Ketik minimal 2 karakter.",
            reply_markup=get_cancel_keyboard(),
        )
        return WAITING_INPUT

    # Simpan nama yang sedang divalidasi
    context.user_data["pending_menu_name"] = menu_name

    token = get_token(context)
    api = get_api_client(settings.backend_url)  # type: ignore[attr-defined]

    await update.message.reply_text("⏳ Memeriksa menu...")

    try:
        resp = await api.post(
            "/mbg/weekly-menus/validate",
            data={"menu_name": menu_name},
            token=token,
        )
        val = resp.get("data", {})
    except Exception as e:
        from utils.api_client import APIError
        if isinstance(e, APIError) and e.status_code in (401, 403): raise e
        await update.message.reply_text(format_error(f"Tidak bisa validasi: {e}"))
        return WAITING_INPUT

    found = val.get("found", False)
    has_bom = val.get("has_bom", False)
    bom_ingredients: list = val.get("bom_ingredients", [])
    product = val.get("product")

    # Simpan hasil validasi di context
    context.user_data["validated_product"] = product  # {id, name} atau None
    context.user_data["pending_has_bom"] = has_bom

    if found and has_bom:
        # KASUS 1: Produk ditemukan + BOM ada
        bom_text = ""
        if bom_ingredients:
            items = [f"{i['name']} {i['qty']}{i['unit']}" for i in bom_ingredients[:5]]
            extra = f" +{len(bom_ingredients)-5} lainnya" if len(bom_ingredients) > 5 else ""
            bom_text = f"\nBOM: {', '.join(items)}{extra}"

        await update.message.reply_text(
            f"✅ *{_esc(menu_name)}*\n"
            f"Produk ditemukan \\| {len(bom_ingredients)} bahan{_esc(bom_text)}\n\n"
            "Simpan untuk hari ini?",
            reply_markup=get_bom_confirm_keyboard(),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return CONFIRM_NO_BOM

    elif found and not has_bom:
        # KASUS 2: Produk ditemukan, BOM kosong
        await update.message.reply_text(
            f"⚠️ *{_esc(menu_name)}* ditemukan tapi belum ada BOM\\.\n\n"
            "Tanpa BOM, stok tidak terpotong otomatis saat penyerahan\\.\n\n"
            "Apa yang mau dilakukan?",
            reply_markup=get_no_bom_keyboard(),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return CONFIRM_NO_BOM

    else:
        # KASUS 3: Produk tidak ditemukan
        await update.message.reply_text(
            f"❓ *'{_esc(menu_name)}'* tidak ada di daftar produk\\.\n\n"
            "Menu baru akan disimpan tanpa koneksi ke stok\\.\n\n"
            "Pilih opsi:",
            reply_markup=get_new_product_keyboard(),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return CONFIRM_NO_BOM


def _esc(text: str) -> str:
    """Escape karakter MarkdownV2."""
    escape_chars = r"\_*[]()~`>#+-=|{}.!"
    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", text)


# ─── CONFIRM_NO_BOM: pilihan simpan ───────────────────────────────────────────

async def _save_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    menu_id: Optional[str] = None,
) -> int:
    """Simpan menu ke backend, refresh tampilan minggu."""
    date_str: str = context.user_data.get("editing_date", "")
    menu_name: str = context.user_data.get("pending_menu_name", "")

    if not date_str or not menu_name:
        if update.callback_query:
            await update.callback_query.edit_message_text(
                format_error("State hilang. Ulangi dari /menu.")
            )
        return ConversationHandler.END

    token = get_token(context)
    api = get_api_client(settings.backend_url)  # type: ignore[attr-defined]

    try:
        await api.post(
            "/mbg/weekly-menus",
            data={"date": date_str, "menu_name": menu_name, "menu_id": menu_id},
            token=token,
        )
    except Exception as e:
        from utils.api_client import APIError
        if isinstance(e, APIError) and e.status_code in (401, 403): raise e
        if update.callback_query:
            await update.callback_query.answer(f"❌ Gagal simpan: {e}", show_alert=True)
        return CONFIRM_NO_BOM

    try:
        d = date.fromisoformat(date_str)
        label = f"{HARI_ID.get(d.weekday()+1, '')} {d.day} {_bulan(d.month)}"
    except Exception:
        label = date_str

    if update.callback_query:
        await update.callback_query.answer(f"✅ Menu {label} disimpan!", show_alert=False)

    ws = context.user_data.get("week_start")
    return await _show_week(update, context, edit=True, week_start=ws)


async def on_confirm_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User klik '💾 Simpan' — menu ditemukan, BOM ada."""
    query = update.callback_query
    if not query:
        return CONFIRM_NO_BOM
    await query.answer()

    product = context.user_data.get("validated_product")
    menu_id = product["id"] if product else None
    return await _save_menu(update, context, menu_id=menu_id)


async def on_save_no_bom(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User klik '⏭️ Simpan Tanpa BOM'."""
    query = update.callback_query
    if not query:
        return CONFIRM_NO_BOM
    await query.answer()
    return await _save_menu(update, context, menu_id=None)


async def on_save_new_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User klik '➕ Simpan sebagai Menu Baru' — produk belum ada, simpan nama saja."""
    query = update.callback_query
    if not query:
        return CONFIRM_NO_BOM
    await query.answer()
    return await _save_menu(update, context, menu_id=None)


async def on_change_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User klik '✏️ Ganti Nama' atau '✏️ Ketik Ulang' — kembali ke input."""
    query = update.callback_query
    if not query:
        return WAITING_INPUT
    await query.answer()

    date_str = context.user_data.get("editing_date", "")
    return await _ask_menu_input(query, context, date_str)


async def on_cancel_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User klik '❌ Batal' — kembali ke tampilan minggu."""
    query = update.callback_query
    if not query:
        return SHOW_WEEK
    await query.answer()
    ws = context.user_data.get("week_start")
    return await _show_week(update, context, edit=True, week_start=ws)


# ─── INPUT_BOM_INLINE: user input bahan BOM ──────────────────────────────────

async def on_input_bom(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User klik '📝 Input BOM Sekarang' — minta user input bahan baris per baris."""
    query = update.callback_query
    if not query:
        return CONFIRM_NO_BOM
    await query.answer()

    menu_name = context.user_data.get("pending_menu_name", "menu")
    context.user_data["bom_lines"] = []  # Reset buffer

    await query.edit_message_text(
        f"🥘 Input bahan untuk *{_esc(menu_name)}*\n\n"
        "Ketik satu bahan per baris dengan format:\n"
        "`nama bahan  qty  satuan`\n\n"
        "Contoh:\n"
        "`Beras 150 gram`\n"
        "`Ayam fillet 100 gram`\n"
        "`Minyak goreng 10 ml`\n\n"
        "Atau tekan tombol di bawah\\:",
        reply_markup=get_bom_cancel_keyboard(),
        parse_mode=ParseMode.MARKDOWN_V2,
    )
    return INPUT_BOM_INLINE


async def on_bom_line_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    User mengetik satu baris BOM.
    Kumpulkan di buffer, konfirmasi setiap baris.
    """
    if not update.message or not update.message.text:
        return INPUT_BOM_INLINE

    line = update.message.text.strip()
    # Parse: nama... qty satuan
    parts = line.rsplit(None, 2)  # split dari kanan maks 2 kali
    if len(parts) < 3:
        await update.message.reply_text(
            "⚠️ Format salah. Gunakan: `nama bahan qty satuan`\n"
            "Contoh: `Beras 150 gram`",
            reply_markup=get_bom_cancel_keyboard(),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return INPUT_BOM_INLINE

    nama, qty_str, satuan = parts[0], parts[1], parts[2]
    try:
        qty = float(qty_str.replace(",", "."))
    except ValueError:
        await update.message.reply_text(
            f"⚠️ Jumlah '{qty_str}' bukan angka yang valid\\.",
            reply_markup=get_bom_cancel_keyboard(),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return INPUT_BOM_INLINE

    bom_lines: list = context.user_data.get("bom_lines", [])
    bom_lines.append({"name": nama, "qty": qty, "unit": satuan})
    context.user_data["bom_lines"] = bom_lines

    await update.message.reply_text(
        f"✅ *{_esc(nama)}* {qty} {_esc(satuan)} dicatat\\.\n"
        f"Total: {len(bom_lines)} bahan\\. Lanjutkan atau tekan Selesai\\.",
        reply_markup=get_bom_cancel_keyboard(),
        parse_mode=ParseMode.MARKDOWN_V2,
    )
    return INPUT_BOM_INLINE


async def on_bom_done_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User klik 'Selesai Input BOM' via inline button."""
    query = update.callback_query
    if not query:
        return INPUT_BOM_INLINE
    await query.answer()
    return await _finalize_bom(update, context)


async def on_bom_done_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User ketik /selesai saat state INPUT_BOM_INLINE."""
    return await _finalize_bom(update, context)


async def _finalize_bom(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Simpan BOM ke backend, lalu simpan menu."""
    bom_lines: list = context.user_data.get("bom_lines", [])
    if not bom_lines:
        msg = "⚠️ Belum ada bahan yang dimasukkan. Ketik minimal 1 bahan."
        if update.callback_query:
            await update.callback_query.edit_message_text(
                msg, reply_markup=get_bom_cancel_keyboard()
            )
        elif update.message:
            await update.message.reply_text(msg, reply_markup=get_bom_cancel_keyboard())
        return INPUT_BOM_INLINE

    product = context.user_data.get("validated_product")
    menu_name = context.user_data.get("pending_menu_name", "")
    token = get_token(context)
    api = get_api_client(settings.backend_url)  # type: ignore[attr-defined]

    saved = 0
    errors = []

    for bom in bom_lines:
        # Cari product_id bahan via GET /products?search=nama
        try:
            prod_resp = await api.get(
                "/products",
                token=token,
                params={"search": bom["name"], "category": "bahan_baku", "limit": 1},
            )
            prods = prod_resp.get("data", [])
            ingredient_id = prods[0]["id"] if prods else None

            if not ingredient_id:
                errors.append(f"'{bom['name']}' tidak ditemukan di produk")
                continue

            if product:
                # Simpan ke tabel recipes
                await api.post(
                    "/recipes",
                    data={
                        "menu_id": product["id"],
                        "ingredient_id": ingredient_id,
                        "qty_needed": bom["qty"],
                        "unit": bom["unit"],
                    },
                    token=token,
                )
                saved += 1
        except Exception as e:
            from utils.api_client import APIError
            if isinstance(e, APIError) and e.status_code in (401, 403): raise e
            errors.append(f"'{bom['name']}': {e}")

    # Beri tahu user hasil
    success_text = f"✅ BOM tersimpan: {saved} dari {len(bom_lines)} bahan"
    if errors:
        success_text += f"\n⚠️ {len(errors)} gagal: {', '.join(errors[:2])}"

    notify_fn = None
    if update.callback_query:
        notify_fn = update.callback_query.edit_message_text
    elif update.message:
        notify_fn = update.message.reply_text

    if notify_fn:
        await notify_fn(success_text)

    # Simpan menu setelah BOM tersimpan
    menu_id = product["id"] if product else None
    return await _save_menu(update, context, menu_id=menu_id)


async def on_cancel_bom(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User batal input BOM — kembali ke pilihan (simpan tanpa BOM / ganti)."""
    query = update.callback_query
    if not query:
        return INPUT_BOM_INLINE
    await query.answer()

    menu_name = context.user_data.get("pending_menu_name", "menu")
    context.user_data["bom_lines"] = []

    await query.edit_message_text(
        f"⚠️ *{_esc(menu_name)}* belum ada BOM\\.\n\n"
        "Apa yang mau dilakukan?",
        reply_markup=get_no_bom_keyboard(),
        parse_mode=ParseMode.MARKDOWN_V2,
    )
    return CONFIRM_NO_BOM


# ─── Cancel global ────────────────────────────────────────────────────────────

async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Fallback /cancel — clear state, kembali ke main menu."""
    _SESSION_KEYS = {"token", "tenant_id", "user_name", "user_role"}
    keys_to_remove = [k for k in context.user_data if k not in _SESSION_KEYS]
    for k in keys_to_remove:
        del context.user_data[k]
    if update.message:
        await update.message.reply_text(
            "✅ Input menu dibatalkan.", reply_markup=get_main_menu(get_role(context) or "")
        )
    return ConversationHandler.END


async def on_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User klik '← Menu Utama' — akhiri conversation."""
    query = update.callback_query
    if not query:
        return ConversationHandler.END
    await query.answer()
    await query.edit_message_text("📋 Kembali ke menu utama.", reply_markup=get_main_menu(get_role(context) or ""))
    _SESSION_KEYS = {"token", "tenant_id", "user_name", "user_role"}
    keys_to_remove = [k for k in context.user_data if k not in _SESSION_KEYS]
    for k in keys_to_remove:
        del context.user_data[k]
    return ConversationHandler.END


# ─── Bangun ConversationHandler ───────────────────────────────────────────────

def build_menu_conversation() -> ConversationHandler:
    """
    Bangun dan kembalikan ConversationHandler untuk /menu.
    Daftarkan di bot/main.py via app.add_handler().
    """
    return ConversationHandler(
        entry_points=[
            CommandHandler("menu", menu_entry),
            CallbackQueryHandler(menu_entry, pattern="^menu_minggu$"),
        ],
        states={
            SHOW_WEEK: [
                CallbackQueryHandler(on_edit_day,    pattern=r"^edit_day_\d{4}-\d{2}-\d{2}$"),
                CallbackQueryHandler(on_change_menu, pattern=r"^change_menu_\d{4}-\d{2}-\d{2}$"),
                CallbackQueryHandler(on_delete_day,  pattern=r"^delete_day_\d{4}-\d{2}-\d{2}$"),
                CallbackQueryHandler(on_back_to_week, pattern="^back_to_week$"),
                CallbackQueryHandler(on_save_week,    pattern="^save_week$"),
                CallbackQueryHandler(on_main_menu,    pattern="^main_menu$"),
            ],
            WAITING_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, on_menu_text_input),
                CallbackQueryHandler(on_cancel_input, pattern="^cancel_input$"),
                CallbackQueryHandler(on_back_to_week, pattern="^back_to_week$"),
            ],
            CONFIRM_NO_BOM: [
                CallbackQueryHandler(on_confirm_save,     pattern="^confirm_save$"),
                CallbackQueryHandler(on_save_no_bom,      pattern="^save_no_bom$"),
                CallbackQueryHandler(on_save_new_product, pattern="^save_new_product$"),
                CallbackQueryHandler(on_change_name,      pattern="^change_name$"),
                CallbackQueryHandler(on_cancel_input,     pattern="^cancel_input$"),
                CallbackQueryHandler(on_input_bom,        pattern="^input_bom$"),
            ],
            INPUT_BOM_INLINE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, on_bom_line_input),
                CommandHandler("selesai", on_bom_done_command),
                CallbackQueryHandler(on_bom_done_callback, pattern="^bom_done$"),
                CallbackQueryHandler(on_cancel_bom,        pattern="^cancel_bom$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_handler),
            CommandHandler("menu", menu_entry),  # restart
        ],
        allow_reentry=True,
        name="menu_conversation",
        persistent=False,
    )
