"""
Telegram Bot main entry point.
Handles initialization, handler registration, dan polling.
"""

import asyncio
import logging

from telegram import BotCommand
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
)

from core.config import settings
from handlers.auth_handler import (
    buka_web,
    error_handler,
    hubungkan_akun,
    logout,
    settings as settings_handler,
    start,
)
from handlers.menu_handler import build_menu_conversation

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def main() -> None:
    """Initialize dan start bot."""
    # Create bot application
    app: Application = Application.builder().token(settings.telegram_bot_token).build()

    # ─── Daftarkan ConversationHandlers (HARUS sebelum CommandHandler biasa) ───
    app.add_handler(build_menu_conversation())

    # ─── Daftarkan command handlers ───
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("logout", logout))
    app.add_handler(CommandHandler("settings", settings_handler))

    # ─── Daftarkan callback handlers ───
    app.add_handler(CallbackQueryHandler(hubungkan_akun, pattern="^hubungkan_akun$"))
    app.add_handler(CallbackQueryHandler(buka_web, pattern="^buka_web$"))

    # ─── Error handler global ───
    app.add_error_handler(error_handler)

    # ─── Setup bot commands ───
    bot_commands = [
        BotCommand("start",    "Login atau lihat menu utama"),
        BotCommand("menu",     "📅 Input menu mingguan Senin–Sabtu"),
        BotCommand("settings", "Lihat pengaturan akun"),
        BotCommand("logout",   "Logout akun"),
        BotCommand("cancel",   "Batalkan proses yang sedang berjalan"),
    ]
    await app.bot.set_my_commands(bot_commands)

    # ─── Start polling ───
    logger.info("Bot starting... Press Ctrl+C to stop")
    async with app:
        await app.run_polling(allowed_updates=[])  # type: ignore[func-returns-value]


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped.")
