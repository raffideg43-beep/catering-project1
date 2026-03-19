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
    except Exception as e:
        from utils.api_client import APIError
        if isinstance(e, APIError) and e.status_code in (401, 403): raise e
        logger.error(f"konfirmasi_serah error: {e}")

        # Try to extract structured error from APIError
        raw = getattr(e, "raw_data", None)
        detail = None
        if raw and isinstance(raw, dict):
            detail = raw.get("detail") or raw
        
        # If detail is still not usable, try parsing the error message string
        if not isinstance(detail, dict):
            msg_str = str(e)
            if "Stok tidak cukup" in msg_str:
                # Try to parse as Python dict literal
                import ast
                try:
                    detail = ast.literal_eval(msg_str)
                except Exception:
                    detail = {"error": "Stok tidak cukup"}
            else:
                detail = {"error": msg_str[:200]} if msg_str else None

        if detail and isinstance(detail, dict):
            resp = {"success": False, "detail": detail}
        else:
            resp = None

    # Bersihkan context
    for k in ("serah_data", "serah_alloc", "editing_school_id"):
        context.user_data.pop(k, None)

    if resp and resp.get("success"):
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

    elif resp and not resp.get("success"):
        detail = resp.get("detail") or resp.get("message", {})
        detail_str = str(detail)
        
        # Detect stock shortage no matter the nesting
        is_stock_error = "Stok tidak cukup" in detail_str
        shortage = []

        if is_stock_error:
            # Try to get shortage details from dictionary
            if isinstance(detail, dict) and "details" in detail:
                 shortage = detail["details"]
            elif isinstance(detail, dict) and "detail" in detail and isinstance(detail["detail"], dict):
                 shortage = detail["detail"].get("details", [])
            elif isinstance(detail, str):
                 try:
                     import ast
                     parsed_dict = ast.literal_eval(detail)
                     shortage = parsed_dict.get("details") or parsed_dict.get("detail", {}).get("details", [])
                 except:
                     pass

        if is_stock_error and shortage:
            lines = [
                "❌ *STOK TIDAK CUKUP*\n",
                "Bahan tidak mencukupi untuk produksi hari ini:\n",
            ]
            for s in shortage[:5]:
                name = _esc(str(s.get('ingredient', '?')))
                unit = _esc(str(s.get('unit', '')))
                needed = s.get('needed', 0)
                available = s.get('available', 0)
                short = s.get('shortage', 0)

                # Format numbers nicely
                def _fmt_num(v):
                    if isinstance(v, str):
                        # if it's already a formatted string like "831.20 kg", just keep the digits/decimals
                        # but it's easier to just escape it
                        return _esc(v.split(' ')[0])
                    try:
                        val = float(v)
                        sval = f"{val:,.2f}".rstrip('0').rstrip('.')
                        return _esc(sval)
                    except Exception:
                        return _esc(str(v))

                lines.append(
                    f"• *{name}*\n"
                    f"  Butuh: {_fmt_num(needed)} {unit}\n"
                    f"  Stok: {_fmt_num(available)} {unit}\n"
                    f"  Kurang: {_fmt_num(short)} {unit}\n"
                )
            lines.append("\n💡 Silakan belanja dulu: /belanja")
            
            try:
                await query.edit_message_text(
                    "\n".join(lines),
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("📝 Catat Belanja", callback_data="belanja"),
                        InlineKeyboardButton("← Menu Utama",    callback_data="main_menu_callback"),
                    ]]),
                    parse_mode="MarkdownV2",
                )
            except Exception as e:
                logger.error(f"Failed to send formatted stock error: {e}")
                # Fallback without markdown
                await query.edit_message_text(
                    "❌ Stok tidak cukup untuk produksi hari ini.\nSilakan belanja bahan dulu: /belanja",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("📝 Catat Belanja", callback_data="belanja"),
                        InlineKeyboardButton("← Menu Utama",    callback_data="main_menu_callback"),
                    ]])
                )
        elif is_stock_error:
            await query.edit_message_text(
                "❌ *Stok tidak cukup untuk produksi hari ini*\n\n"
                "Silakan belanja bahan dulu /belanja",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("📝 Catat Belanja", callback_data="belanja"),
                    InlineKeyboardButton("← Menu Utama",    callback_data="main_menu_callback"),
                ]]),
                parse_mode="MarkdownV2",
            )
        else:
            # Generic error — extract human message
            if isinstance(detail, dict):
                err_msg = str(detail.get("error") or detail.get("message") or detail.get("detail") or "Terjadi kesalahan")
            elif isinstance(detail, str):
                err_msg = detail
            else:
                err_msg = str(detail)
            
            # Remove any dict/json looking text
            if err_msg.startswith("{") or err_msg.startswith("["):
                # Try simple dict extraction one last time
                try:
                    import ast
                    d = ast.literal_eval(err_msg)
                    err_msg = d.get("error") or d.get("detail") or "Terjadi kesalahan saat memproses"
                    if isinstance(err_msg, dict):
                         err_msg = err_msg.get("error") or "Terjadi kesalahan saat memproses"
                except:
                    err_msg = "Terjadi kesalahan saat memproses"
            
            if len(str(err_msg)) > 200:
                err_msg = str(err_msg)[:197] + "..."
                
            try:
                await query.edit_message_text(
                    f"❌ *Gagal*\n\n{_esc(str(err_msg))}\n\nSilakan coba lagi\\.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔄 Coba Lagi", callback_data="retry_serah"),
                        InlineKeyboardButton("← Menu Utama", callback_data="main_menu_callback"),
                    ]]),
                    parse_mode="MarkdownV2",
                )
            except Exception:
                await query.edit_message_text(
                    f"❌ Gagal\n\n{str(err_msg)}\n\nSilakan coba lagi.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔄 Coba Lagi", callback_data="retry_serah"),
                        InlineKeyboardButton("← Menu Utama", callback_data="main_menu_callback"),
                    ]])
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
