"""
bot/core/error_handler.py
Global error handler untuk python-telegram-bot.
"""

import logging
import traceback

from telegram import Update
from telegram.error import Conflict, Forbidden, NetworkError, TimedOut
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler error global.
    - NetworkError / TimedOut / Conflict → log warning, tidak ganggu user
    - Forbidden (bot diblock) → log info
    - Lainnya → log error + kirim pesan ke user jika bisa
    """
    err = context.error

    # ─── Network issues — bot akan retry sendiri ──────────────────────
    if isinstance(err, (NetworkError, TimedOut, Conflict)):
        logger.warning("Network issue/Conflict (ignored): %s", type(err).__name__)
        return

    # ─── Bot diblok user ──────────────────────────────────────────────
    if isinstance(err, Forbidden):
        user_id = None
        if isinstance(update, Update) and update.effective_user:
            user_id = update.effective_user.id
        logger.info("Bot diblok oleh user_id=%s", user_id)
        return

    # ─── Error lain — log + beritahu user ────────────────────────────
    logger.error("Unhandled error: %s", err, exc_info=True)

    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "❌ Terjadi kesalahan. Coba lagi atau ketik /start untuk mulai ulang."
            )
        except Exception:
            pass  # Jangan raise jika kirim pesan gagal
