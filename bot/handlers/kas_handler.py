"""
bot/handlers/kas_handler.py
Command /kas — Cek saldo kas dan ringkasan anggaran MBG.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from utils.api_client import api_get
from utils.session import get_user_data
from utils.formatter import format_rp

logger = logging.getLogger(__name__)


async def kas_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler untuk command /kas — tampilkan saldo kas dan ringkasan anggaran."""
    user_data = get_user_data(context)
    if not user_data:
        await update.message.reply_text("❌ Anda belum login. Ketik /start untuk login.")
        return

    token = user_data.get("token", "")
    role = user_data.get("role", "kasir")

    if role not in ("owner", "admin"):
        await update.message.reply_text("❌ Hanya owner dan admin yang bisa melihat saldo kas.")
        return

    await update.message.reply_text("⏳ Mengambil data kas...")

    try:
        resp = await api_get("/budget/summary", token=token)
        data = resp.get("data", {}) if resp else {}
    except Exception as e:
        logger.error(f"Error fetching budget summary: {e}")
        await update.message.reply_text("❌ Gagal mengambil data anggaran. Coba lagi nanti.")
        return

    if not data:
        await update.message.reply_text(
            "ℹ️ Belum ada data anggaran.\n\n"
            "Untuk memulai:\n"
            "1. Buka Web → 📊 Anggaran\n"
            "2. Set Pagu bulan ini\n"
            "3. Catat Pencairan dana\n"
            "4. Tambahkan Kas (VA Bank, Kas Kecil)"
        )
        return

    # ── Format saldo kas ──
    kas_balances = data.get("kas_balances", [])
    if kas_balances:
        kas_lines = "\n".join(
            f"   {k['name']:.<20s} {format_rp(float(k['balance']))}"
            for k in kas_balances
        )
        total_kas = sum(float(k["balance"]) for k in kas_balances)
        kas_section = f"   {'─' * 30}\n   {'Total':<20s} {format_rp(total_kas)}"
    else:
        kas_lines = "   (Belum ada kas. Tambahkan di Web → Anggaran)"
        kas_section = ""

    # ── Format ringkasan ──
    pagu = format_rp(float(data.get("pagu_amount", 0)))
    cair = format_rp(float(data.get("total_disbursed", 0)))
    terpakai = format_rp(float(data.get("total_spent", 0)))
    sisa = format_rp(float(data.get("sisa_anggaran", 0)))
    pct = data.get("pct_terpakai", 0)
    porsi = data.get("total_porsi", 0)

    from datetime import date
    today = date.today()
    tgl = today.strftime("%d %B %Y")

    msg = (
        f"🏦 *SALDO KAS*\n"
        f"_{tgl}_\n"
        f"{'─' * 30}\n"
        f"{kas_lines}\n"
        f"{kas_section}\n\n"
        f"📊 *RINGKASAN ANGGARAN*\n"
        f"{'─' * 30}\n"
        f"   Pagu bulan ini : {pagu}\n"
        f"   Total cair     : {cair}\n"
        f"   Terpakai       : {terpakai} ({pct}%)\n"
        f"   Sisa           : {sisa}\n"
        f"   Total porsi    : {porsi:,}\n"
    )

    sisa_val = float(data.get("sisa_anggaran", 0))
    if sisa_val > 0 and not data.get("fund_return"):
        msg += f"\n⚠️ *Sisa {sisa} wajib dikembalikan ke kas negara*\n"

    keyboard = [[InlineKeyboardButton("📊 Lihat Detail di Web", url="http://localhost:3000/anggaran")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        msg,
        parse_mode="Markdown",
        reply_markup=reply_markup,
    )
