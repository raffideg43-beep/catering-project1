"""
bot/handlers/serah_handler.py
Konfirmasi penyerahan MBG harian via /serah — Modul 10

ConversationHandler, maks 3 langkah:
  Langkah 1 (INPUT_PORTIONS): Tampil daftar sekolah + porsi default
  Langkah 2 (CONFIRM_SERAH) : Ringkasan + estimasi alokasi → konfirmasi
  Langkah 3 (DONE)          : POST /mbg/deliveries/bulk → hasil
"""

import logging
import re
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from core.config import settings
from utils.api_client import get_api_client
from utils.formatter import format_error
from utils.session import get_role, get_token, is_authenticated

logger = logging.getLogger(__name__)

# ─── States ───────────────────────────────────────────────────────────────────
INPUT_PORTIONS = 0
CONFIRM_SERAH = 1

CAN_INPUT_ROLES = {"owner", "admin", "kasir"}
HARI_INDO = {
    "Monday": "Senin", "Tuesday": "Selasa", "Wednesday": "Rabu",
    "Thursday": "Kamis", "Friday": "Jumat", "Saturday": "Sabtu",
    "Sunday": "Minggu",
}


def _can_input(context: ContextTypes.DEFAULT_TYPE) -> bool:
    return get_role(context) in CAN_INPUT_ROLES


def _fmt_rp(amount) -> str:
    try:
        return f"Rp {int(Decimal(str(amount or 0))):,}".replace(",", ".")
    except Exception:
        return f"Rp {amount}"


def _esc(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"([_*\[\]()~`>#+\-=|{}.!\\])", r"\\\1", str(text))


def _serah_keyboard(schools: dict) -> InlineKeyboardMarkup:
    """Tombol tiap sekolah + Lanjut + Batal."""
    buttons = []
    for sid, info in schools.items():
        nama = info["name"][:28]
        porsi = info["portions"]
        buttons.append([InlineKeyboardButton(
            f"✏️ {nama} — {porsi} porsi",
            callback_data=f"edit_porsi_{sid}",
        )])
    buttons.append([
        InlineKeyboardButton("✅ Lanjut dengan Kuota Default", callback_data="serah_lanjut"),
    ])
    buttons.append([
        InlineKeyboardButton("❌ Batal", callback_data="serah_batal"),
    ])
    return InlineKeyboardMarkup(buttons)


# ─── Entry Point: /serah ──────────────────────────────────────────────────────

async def serah_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = update.effective_message
    if not msg:
        return ConversationHandler.END

    if not is_authenticated(context):
        if update.callback_query:
            await update.callback_query.answer("❌ Sesi log off. Ketik /start untuk memuat ulang.", show_alert=True)
        else:
            await msg.reply_text("❌ Silakan /start dulu untuk login.")
        return ConversationHandler.END

    if not _can_input(context):
        await msg.reply_text("❌ Hanya owner, admin, dan kasir yang bisa konfirmasi serah.")
        return ConversationHandler.END

    token = get_token(context)
    api = get_api_client(settings.backend_url)

    # Ambil menu hari ini, daftar sekolah, alokasi settings secara parallel-like
    try:
        menu_resp = await api.get("/mbg/weekly-menus/today", token=token)
        schools_resp = await api.get("/schools?is_active=true&limit=50", token=token)
    except Exception as e:
        from utils.api_client import APIError
        if isinstance(e, APIError) and e.status_code in (401, 403): raise e
        await msg.reply_text(format_error(f"Gagal ambil data: {e}"))
        return ConversationHandler.END

    menu_data = (menu_resp or {}).get("data")
    menu_name = (menu_data or {}).get("menu_name", "Belum diset")
    schools_raw: list = (schools_resp or {}).get("data", [])

    if not schools_raw:
        await msg.reply_text(
            "❌ Tidak ada sekolah aktif\\. Tambah sekolah di web dashboard dulu\\.",
            parse_mode="MarkdownV2",
        )
        return ConversationHandler.END

    today = date.today()
    hari = HARI_INDO.get(today.strftime("%A"), today.strftime("%A"))
    tanggal = today.strftime("%d/%m/%Y")

    # Bangun schools dict dengan default = default_portions
    schools: Dict[str, dict] = {}
    for s in schools_raw:
        sid = s.get("id", "")
        if not sid:
            continue
        schools[sid] = {
            "name": s.get("name") or "Sekolah",
            "portions": int(s.get("default_portions") or s.get("quota") or 100),
        }

    context.user_data["serah_data"] = {
        "delivery_date": today.isoformat(),
        "schools": schools,
        "menu_name": menu_name,
    }
    context.user_data.pop("editing_school_id", None)

    await msg.reply_text(
        f"🍱 *KONFIRMASI PENYERAHAN MBG*\n"
        f"📅 {_esc(hari)}, {_esc(tanggal)}\n"
        f"🍽️ Menu: {_esc(menu_name)}\n\n"
        f"Tap sekolah untuk edit porsi, atau klik Lanjut:",
        reply_markup=_serah_keyboard(schools),
        parse_mode="MarkdownV2",
    )
    return INPUT_PORTIONS


# ─── Callback: edit porsi per sekolah ────────────────────────────────────────

async def edit_porsi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not query:
        return INPUT_PORTIONS
    await query.answer()

    school_id = query.data.replace("edit_porsi_", "")
    serah_data = context.user_data.get("serah_data", {})
    school = serah_data.get("schools", {}).get(school_id, {})
    nama = school.get("name", "Sekolah")
    default_porsi = school.get("portions", 100)

    context.user_data["editing_school_id"] = school_id

    await query.edit_message_text(
        f"✏️ *Edit Porsi: {_esc(nama)}*\n\n"
        f"Kuota default: {_esc(str(default_porsi))} porsi\n\n"
        "Ketik jumlah porsi yang dikirim hari ini:",
        parse_mode="MarkdownV2",
    )
    return INPUT_PORTIONS


async def handle_porsi_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Terima angka porsi setelah user tap edit sekolah."""
    if not update.message or not update.message.text:
        return INPUT_PORTIONS

    school_id = context.user_data.get("editing_school_id")
    if not school_id:
        return INPUT_PORTIONS

    text = update.message.text.strip()
    try:
        porsi = int(text)
        if porsi <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            "❌ Jumlah porsi harus angka positif\\. Coba lagi:",
            parse_mode="MarkdownV2",
        )
        return INPUT_PORTIONS

    serah_data = context.user_data.get("serah_data", {})
    schools = serah_data.get("schools", {})
    if school_id in schools:
        schools[school_id]["portions"] = porsi

    context.user_data.pop("editing_school_id", None)

    # Kembali ke tampilan daftar sekolah
    hari = HARI_INDO.get(date.today().strftime("%A"), "")
    menu_name = serah_data.get("menu_name", "Belum diset")
    tanggal = date.today().strftime("%d/%m/%Y")

    await update.message.reply_text(
        f"🍱 *KONFIRMASI PENYERAHAN MBG*\n"
        f"📅 {_esc(hari)}, {_esc(tanggal)}\n"
        f"🍽️ Menu: {_esc(menu_name)}\n\n"
        f"✅ {_esc(schools[school_id]['name'])}: *{porsi} porsi* diupdate\n\n"
        "Tap sekolah untuk edit porsi, atau klik Lanjut:",
        reply_markup=_serah_keyboard(schools),
        parse_mode="MarkdownV2",
    )
    return INPUT_PORTIONS


# ─── Callback: serah_lanjut → tampil ringkasan konfirmasi ────────────────────

async def serah_lanjut(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not query:
        return CONFIRM_SERAH
    await query.answer()

    serah_data = context.user_data.get("serah_data", {})
    schools = serah_data.get("schools", {})
    menu_name = serah_data.get("menu_name", "Belum diset")

    total_portions = sum(s["portions"] for s in schools.values())

    # Ambil alokasi settings dari backend
    token = get_token(context)
    api = get_api_client(settings.backend_url)
    try:
        settings_resp = await api.get("/mbg/allocation-settings", token=token)
        alloc_set = (settings_resp or {}).get("data", {})
    except Exception:
        alloc_set = {}

    price_per_portion = float(alloc_set.get("price_per_portion") or 15000)
    food_pct  = float(alloc_set.get("food_pct")  or 0.80)
    labor_pct = float(alloc_set.get("labor_pct") or 0.15)
    ops_pct   = float(alloc_set.get("ops_pct")   or 0.05)

    total_rev  = price_per_portion * total_portions
    budget_food  = round(total_rev * food_pct, 0)
    budget_labor = round(total_rev * labor_pct, 0)
    budget_ops   = round(total_rev * ops_pct, 0)

    # Simpan estimasi alokasi untuk submit
    context.user_data["serah_alloc"] = {
        "total_revenue": total_rev,
        "budget_food": budget_food,
        "budget_labor": budget_labor,
        "budget_ops": budget_ops,
    }

    lines = ["📋 *RINGKASAN PENYERAHAN*\n"]
    for info in schools.values():
        lines.append(f"• {_esc(info['name'])}: {info['portions']} porsi")
    lines.append(f"\n━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"*Total: {total_portions} porsi*")
    lines.append(f"\n💰 *Estimasi Pendapatan:*")
    lines.append(f"Gross    : {_esc(_fmt_rp(total_rev))}")
    lines.append(f"PPh 22   : ditentukan saat laporan")
    lines.append(f"Bersih   : \\~{_esc(_fmt_rp(total_rev))}")
    lines.append(f"\n📊 *Alokasi:*")
    lines.append(f"Bahan  : {_esc(_fmt_rp(budget_food))} \\({int(food_pct*100)}%\\)")
    lines.append(f"Upah   : {_esc(_fmt_rp(budget_labor))} \\({int(labor_pct*100)}%\\)")
    lines.append(f"Ops    : {_esc(_fmt_rp(budget_ops))} \\({int(ops_pct*100)}%\\)")

    await query.edit_message_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Konfirmasi Serah", callback_data="konfirmasi_serah"),
            InlineKeyboardButton("✏️ Edit",             callback_data="edit_kembali"),
            InlineKeyboardButton("❌ Batal",             callback_data="serah_batal"),
        ]]),
        parse_mode="MarkdownV2",
    )
    return CONFIRM_SERAH


# ─── Callback: konfirmasi_serah → POST ke backend ────────────────────────────

async def konfirmasi_serah(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not query:
        return ConversationHandler.END
    await query.answer("Mengirim data...")

    serah_data = context.user_data.get("serah_data", {})
    schools: dict = serah_data.get("schools", {})
    delivery_date: str = serah_data.get("delivery_date", date.today().isoformat())

    token = get_token(context)
    api = get_api_client(settings.backend_url)

    payload = {
        "delivery_date": delivery_date,
        "deliveries": [
            {"school_id": sid, "portions_sent": info["portions"], "receiver_name": None}
            for sid, info in schools.items()
        ],
    }

    try:
        resp = await api.post("/mbg/deliveries/bulk", token=token, json=payload)
        
        # Bersihkan context jika sukses
        for k in ("serah_data", "serah_alloc", "editing_school_id"):
            context.user_data.pop(k, None)

        data = resp.get("data", {})
        total_p = data.get("total_portions", 0)
        total_s = data.get("total_schools", 0)
        alloc = data.get("allocation", {})
        total_rev = alloc.get("total_revenue", 0)
        has_pdf = bool(data.get("pdf_draft_url"))
        warning = data.get("warning")

        warn_note = f"\n⚠️ _{_esc(warning)}_" if warning else ""

        await query.edit_message_text(
            f"✅ *Penyerahan dikonfirmasi\\!*\n\n"
            f"🍱 *{total_p} porsi* ke {total_s} sekolah\n"
            f"💰 Piutang: {_esc(_fmt_rp(total_rev))}\n"
            f"{'📄 Draft nota PDF disiapkan' if has_pdf else '📄 PDF tidak tersedia \\(ReportLab\\)'}\n"
            f"📊 Excel sedang diperbarui\\.\\.\\."
            f"{warn_note}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("← Menu Utama", callback_data="main_menu_callback"),
            ]]),
            parse_mode="MarkdownV2",
        )

    except Exception as e:
        from utils.api_client import APIError
        if isinstance(e, APIError) and e.status_code in (401, 403):
            raise e
        logger.error(f"konfirmasi_serah error: {e}")

        if isinstance(e, APIError) and e.status_code == 400:
            error_data = getattr(e, "response_json", {})
            if (isinstance(error_data, dict)
                and error_data.get("error") == "Stok tidak cukup"
                and "details" in error_data):
                
                details = error_data["details"]
                lines = []
                
                for item in details:
                    # Convert base unit ke display unit
                    needed_base = item.get("needed", 0)
                    available_base = item.get("available", 0)
                    shortage_base = item.get("shortage", 0)
                    ingredient = item.get("ingredient", "?")
                    
                    # Ambil conversion factor dari produk (dari API)
                    base_unit = item.get("base_unit", "gram")
                    display_unit = item.get("display_unit", "kg")
                    factor = item.get("conversion_factor", 1000)
                    
                    if not factor or factor == 0:
                        factor = 1000
                        if base_unit == "pcs":
                            factor = 1
                            display_unit = "pcs"
                        elif base_unit == "ml":
                            factor = 1000
                            display_unit = "liter"
                    
                    needed_display = needed_base / factor
                    available_display = available_base / factor
                    shortage_display = shortage_base / factor

                    nd_str = f"{needed_display:.2f}".rstrip('0').rstrip('.')
                    ad_str = f"{available_display:.2f}".rstrip('0').rstrip('.')
                    sd_str = f"{shortage_display:.2f}".rstrip('0').rstrip('.')
                    
                    lines.append(
                        f"• {_esc(ingredient)}\n"
                        f"  Butuh : {_esc(nd_str)} {_esc(display_unit)}\n"
                        f"  Stok  : {_esc(ad_str)} {_esc(display_unit)}\n"
                        f"  Kurang: {_esc(sd_str)} {_esc(display_unit)}"
                    )
                
                detail_text = "\n\n".join(lines)
                msg = (
                    f"❌ *STOK TIDAK CUKUP*\n\n"
                    f"Bahan tidak mencukupi untuk produksi:\n\n"
                    f"{detail_text}\n\n"
                    f"💡 Silakan belanja dulu: /belanja"
                )
            else:
                raw_err = error_data.get('error', 'Unknown error') if isinstance(error_data, dict) else 'Unknown error'
                msg = f"❌ *Gagal:* {_esc(str(raw_err))}"

            try:
                await query.edit_message_text(
                    msg,
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("📝 Catat Belanja", callback_data="belanja")],
                        [InlineKeyboardButton("← Menu Utama", callback_data="main_menu_callback")]
                    ]),
                    parse_mode="MarkdownV2"
                )
            except Exception as e2:
                logger.error(f"Failed to send formatted stock error (markdown error): {e2}")
                # Fallback without markdown
                await query.edit_message_text(
                    "❌ Stok tidak cukup untuk produksi hari ini.\nSilakan belanja bahan dulu: /belanja",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("📝 Catat Belanja", callback_data="belanja")],
                        [InlineKeyboardButton("← Menu Utama", callback_data="main_menu_callback")]
                    ])
                )

        elif isinstance(e, APIError) and e.status_code >= 500:
            await query.edit_message_text(
                "❌ *Server bermasalah*\\. Coba lagi\\.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("← Menu Utama", callback_data="main_menu_callback")
                ]]),
                parse_mode="MarkdownV2"
            )
        else:
            msg = getattr(e, "message", str(e))
            if len(str(msg)) > 200:
                msg = str(msg)[:197] + "..."
            try:
                await query.edit_message_text(
                    f"❌ *Gagal:* \n\n_{_esc(str(msg))}_\n\nSilakan coba lagi\\.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔄 Coba Lagi", callback_data="retry_serah")],
                        [InlineKeyboardButton("← Menu Utama", callback_data="main_menu_callback")]
                    ]),
                    parse_mode="MarkdownV2"
                )
            except Exception:
                await query.edit_message_text(
                    f"❌ Gagal: Terjadi kesalahan saat memproses",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔄 Coba Lagi", callback_data="retry_serah")],
                        [InlineKeyboardButton("← Menu Utama", callback_data="main_menu_callback")],
                    ])
                )
    else:
        await query.edit_message_text(
            "❌ *Gagal koneksi ke server*\n\nSilakan coba lagi nanti\\.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("← Menu Utama", callback_data="main_menu_callback"),
            ]]),
            parse_mode="MarkdownV2",
        )

    return ConversationHandler.END


# ─── Callback: edit_kembali → kembali ke tampilan sekolah ────────────────────

async def edit_kembali(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not query:
        return INPUT_PORTIONS
    await query.answer()

    serah_data = context.user_data.get("serah_data", {})
    schools = serah_data.get("schools", {})
    menu_name = serah_data.get("menu_name", "Belum diset")
    hari = HARI_INDO.get(date.today().strftime("%A"), "")
    tanggal = date.today().strftime("%d/%m/%Y")

    await query.edit_message_text(
        f"🍱 *KONFIRMASI PENYERAHAN MBG*\n"
        f"📅 {_esc(hari)}, {_esc(tanggal)}\n"
        f"🍽️ Menu: {_esc(menu_name)}\n\n"
        "Tap sekolah untuk edit porsi, atau klik Lanjut:",
        reply_markup=_serah_keyboard(schools),
        parse_mode="MarkdownV2",
    )
    return INPUT_PORTIONS


# ─── Callback batal ───────────────────────────────────────────────────────────

async def serah_batal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not query:
        return ConversationHandler.END
    await query.answer()

    for k in ("serah_data", "serah_alloc", "editing_school_id"):
        context.user_data.pop(k, None)

    await query.edit_message_text("❌ Penyerahan MBG dibatalkan\\.", parse_mode="MarkdownV2")
    return ConversationHandler.END


async def cancel_serah(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    for k in ("serah_data", "serah_alloc", "editing_school_id"):
        context.user_data.pop(k, None)
    if update.message:
        await update.message.reply_text("❌ Dibatalkan\\.", parse_mode="MarkdownV2")
    return ConversationHandler.END


# ─── Build ConversationHandler ────────────────────────────────────────────────

def build_serah_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("serah", serah_entry),
            CallbackQueryHandler(serah_entry, pattern="^serah$"),
        ],
        states={
            INPUT_PORTIONS: [
                CallbackQueryHandler(edit_porsi,       pattern=r"^edit_porsi_"),
                CallbackQueryHandler(serah_lanjut,     pattern=r"^serah_lanjut$"),
                CallbackQueryHandler(serah_batal,      pattern=r"^serah_batal$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_porsi_input),
            ],
            CONFIRM_SERAH: [
                CallbackQueryHandler(konfirmasi_serah, pattern=r"^konfirmasi_serah$"),
                CallbackQueryHandler(edit_kembali,     pattern=r"^edit_kembali$"),
                CallbackQueryHandler(serah_batal,      pattern=r"^serah_batal$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_serah),
            CommandHandler("start",  cancel_serah),
        ],
        allow_reentry=True,
        name="serah_conversation",
    )
