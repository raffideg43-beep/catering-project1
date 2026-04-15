import logging
from datetime import date
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CommandHandler

from core.config import settings
from keyboards.main_menu import get_main_menu
from utils.api_client import get_api_client
from utils.formatter import format_error
from utils.session import is_authenticated, get_token, get_role

logger = logging.getLogger(__name__)

async def nutrisi_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pengecekan Nutrisi & Kalori hari ini."""
    if not is_authenticated(context):
        await update.message.reply_text("❌ Silakan /start dulu untuk login.")
        return

    role = get_role(context)
    if role not in ["owner", "admin"]:
        await update.message.reply_text("⛔ Akses Ditolak. Fitur ini hanya untuk Owner/Admin.")
        return

    token = get_token(context)
    api = get_api_client(settings.backend_url)
    today_str = date.today().isoformat()

    await update.message.reply_text("⏳ Memeriksa data gizi hari ini...")

    try:
        resp = await api.get("/nutrition/calendar", token=token, params={"target_date": today_str})
        data = resp.get("data", [])
    except Exception as e:
        await update.message.reply_text(format_error(f"Gagal mengambil kalender gizi: {e}"))
        return

    today_data = next((d for d in data if d["date"] == today_str), None)
    
    if not today_data or not today_data.get("menu_name"):
        await update.message.reply_text("📅 Hari ini tidak ada menu tersimpan.")
        return

    menu_name = today_data["menu_name"]
    nut = today_data.get("nutrition", {})
    issues = today_data.get("issues", [])
    
    lines = [
        f"🩺 <b>Status Gizi MBG Hari Ini</b>",
        f"📅 Tanggal: {today_str}",
        f"🍽️ Menu: <b>{menu_name}</b>",
        "",
        "📊 <b>Kandungan per Porsi:</b>",
        f"• Energi: {nut.get('energi', 0):.1f} kkal",
        f"• Protein: {nut.get('protein', 0):.1f} gr",
        f"• Lemak: {nut.get('lemak', 0):.1f} gr",
        f"• Karbo: {nut.get('karbo', 0):.1f} gr",
        f"• Netto Bahan: {nut.get('weight', 0):.1f} gr",
        ""
    ]

    porsi_sayur = nut.get("porsi_sayur", 0)
    lines.append(f"🥬 <b>Porsi Sayur:</b> {porsi_sayur:.0f}%")

    if issues:
        lines.append("")
        lines.append("⚠️ <b>ATENSI DINAS (TIDAK MEMENUHI STANDAR):</b>")
        for i in issues:
            lines.append(f"❌ {i}")
    else:
        lines.append("\n✅ <b>Gizi Memenuhi Standar Nasional</b>")

    keyboard = [[InlineKeyboardButton("📋 Menu Utama", callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            "\n".join(lines),
            parse_mode="HTML",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            "\n".join(lines),
            parse_mode="HTML",
            reply_markup=reply_markup
        )

async def cek_gizi_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await nutrisi_command(update, context)

def setup_nutrisi_handler(app) -> None:
    app.add_handler(CommandHandler("nutrisi", nutrisi_command))
    from telegram.ext import CallbackQueryHandler
    app.add_handler(CallbackQueryHandler(cek_gizi_cb, pattern="^cek_gizi$"))
