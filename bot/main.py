"""
Telegram Bot main entry point.
Handles initialization, handler registration, dan polling.
"""

import asyncio
import logging
import sys

from telegram import BotCommand
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from core.config import settings
from core.error_handler import error_handler as bot_error_handler
from handlers.auth_handler import (
    buka_web,
    error_handler as auth_error_handler,
    hubungkan_akun,
    logout,
    settings as settings_handler,
    start,
)

from handlers.menu_handler import build_menu_conversation
from handlers.belanja_handler import build_belanja_conversation
from handlers.serah_handler import build_serah_conversation
from handlers.report_handler import (
    hariini_command,
    laporan_command,
    stok_command,
    piutang_command,
    hutang_command,
    lunas_hutang,
    laporan_hariini_cb,
    laporan_bulanan_cb,
    cek_stok_cb,
    download_excel_cb,
)
from handlers.nota_handler import (
    cancel_nota,
    confirm_nota,
    edit_item,
    edit_nota,
    handle_photo,
    handle_text_input,
    selesai_kirim,
    konfirmasi_semua,
    batal_semua,
    kirim_ulang,
)

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def main() -> None:
    """Initialize dan start bot."""
    app: Application = Application.builder().token(settings.telegram_bot_token).build()

    # ─── ConversationHandlers HARUS sebelum handler biasa ───────────
    app.add_handler(build_menu_conversation())
    app.add_handler(build_serah_conversation())
    app.add_handler(build_belanja_conversation())

    # ─── Foto nota — MessageHandler ──────────────────────────────────
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # ─── Text handler: edit item inline ──────────────────────────────
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, handle_text_input
    ))

    # ─── Command handlers ─────────────────────────────────────────────
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("logout", logout))
    app.add_handler(CommandHandler("settings", settings_handler))

    # ─── Command handlers: laporan ────────────────────────────────────
    app.add_handler(CommandHandler("hariini", hariini_command))
    app.add_handler(CommandHandler("laporan", laporan_command))
    app.add_handler(CommandHandler("stok",    stok_command))
    app.add_handler(CommandHandler("piutang", piutang_command))
    app.add_handler(CommandHandler("hutang",  hutang_command))

    # ─── Callback handlers: report shortcuts ─────────────────────────
    app.add_handler(CallbackQueryHandler(laporan_hariini_cb, pattern=r"^laporan_hariini$"))
    app.add_handler(CallbackQueryHandler(laporan_bulanan_cb, pattern=r"^laporan_bulanan$"))
    app.add_handler(CallbackQueryHandler(cek_stok_cb,        pattern=r"^cek_stok$"))
    app.add_handler(CallbackQueryHandler(lunas_hutang,       pattern=r"^lunas_hutang_"))
    app.add_handler(CallbackQueryHandler(download_excel_cb,  pattern=r"^download_excel_"))


    # ─── Callback handlers: nota (confirm / edit / cancel / edit_item) ─
    app.add_handler(CallbackQueryHandler(confirm_nota, pattern=r"^confirm_[a-f0-9\-]{36}$"))
    app.add_handler(CallbackQueryHandler(edit_nota,    pattern=r"^edit_[a-f0-9\-]{36}$"))
    app.add_handler(CallbackQueryHandler(cancel_nota,  pattern=r"^cancel_[a-f0-9\-]{36}$"))
    app.add_handler(CallbackQueryHandler(edit_item,    pattern=r"^edit_item_"))

    # ─── Callback handlers: batch ────────────────────────────────────
    app.add_handler(CallbackQueryHandler(selesai_kirim,    pattern=r"^selesai_kirim$"))
    app.add_handler(CallbackQueryHandler(konfirmasi_semua, pattern=r"^konfirmasi_semua_"))
    app.add_handler(CallbackQueryHandler(batal_semua,      pattern=r"^batal_semua_"))
    app.add_handler(CallbackQueryHandler(kirim_ulang,      pattern=r"^kirim_ulang_"))

    # ─── Callback handlers: auth / navigation ────────────────────────
    app.add_handler(CallbackQueryHandler(hubungkan_akun, pattern="^hubungkan_akun$"))
    app.add_handler(CallbackQueryHandler(buka_web,       pattern="^buka_web$"))

    # ─── Error handlers ───────────────────────────────────────────────
    # Global handler dari core/ menangani Network, Forbidden, dan lain-lain
    app.add_error_handler(bot_error_handler)
    # Auth-specific handler sebagai fallback di auth_handler
    # (tidak di-register lagi di sini karena bot_error_handler sudah cover)

    # ─── Bot commands menu ────────────────────────────────────────────
    bot_commands = [
        BotCommand("start",    "Login atau lihat menu utama"),
        BotCommand("serah",    "🍱 Konfirmasi penyerahan MBG"),
        BotCommand("menu",     "📅 Input menu mingguan Senin–Sabtu"),
        BotCommand("belanja",  "📝 Input belanja manual"),
        BotCommand("hariini",  "📊 Ringkasan hari ini"),
        BotCommand("laporan",  "📈 Laporan bulan ini"),
        BotCommand("stok",     "📦 Status stok bahan"),
        BotCommand("piutang",  "💰 Tagihan MBG belum lunas"),
        BotCommand("hutang",   "💸 Hutang ke supplier"),
        BotCommand("settings", "Lihat pengaturan akun"),
        BotCommand("logout",   "Logout akun"),
        BotCommand("cancel",   "Batalkan proses yang sedang berjalan"),
    ]
    await app.bot.set_my_commands(bot_commands)

    logger.info("Bot starting... Press Ctrl+C to stop")

    # Jalankan app.run_polling() langsung (bukan di dalam coroutine).
    # Ini dipanggil dari __main__ block secara synchronous.
    raise _RunPollingSignal(app)


class _RunPollingSignal(Exception):
    """Internal signal untuk menjalankan run_polling dari luar coroutine."""
    def __init__(self, app):
        self.app = app


if __name__ == "__main__":
    # Python 3.13 + Windows: set SelectorEventLoop
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    import asyncio as _asyncio

    # Build app dulu di sync context
    async def _build():
        return await _create_app()

    async def _create_app():
        from core.config import settings as _settings
        from core.error_handler import error_handler as bot_error_handler
        from handlers.auth_handler import (
            buka_web, error_handler as auth_error_handler,
            hubungkan_akun, logout, settings as settings_handler, start,
        )
        from handlers.menu_handler import build_menu_conversation
        from handlers.belanja_handler import build_belanja_conversation
        from handlers.serah_handler import build_serah_conversation
        from handlers.report_handler import (
            hariini_command, laporan_command, stok_command,
            piutang_command, hutang_command, lunas_hutang,
            laporan_hariini_cb, laporan_bulanan_cb, cek_stok_cb, download_excel_cb,
        )
        from handlers.nota_handler import (
            cancel_nota, confirm_nota, edit_item, edit_nota,
            handle_photo, handle_text_input, selesai_kirim,
            konfirmasi_semua, batal_semua, kirim_ulang,
        )

        from telegram import BotCommand
        from telegram.ext import (
            Application, CallbackQueryHandler, CommandHandler,
            MessageHandler, filters,
        )

        app = Application.builder().token(_settings.telegram_bot_token).build()

        app.add_handler(build_menu_conversation())
        app.add_handler(build_serah_conversation())
        app.add_handler(build_belanja_conversation())
        app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input))
        app.add_handler(CommandHandler("start",    start))
        app.add_handler(CommandHandler("logout",   logout))
        app.add_handler(CommandHandler("settings", settings_handler))
        app.add_handler(CommandHandler("hariini",  hariini_command))
        app.add_handler(CommandHandler("laporan",  laporan_command))
        app.add_handler(CommandHandler("stok",     stok_command))
        app.add_handler(CommandHandler("piutang",  piutang_command))
        app.add_handler(CommandHandler("hutang",   hutang_command))
        app.add_handler(CallbackQueryHandler(laporan_hariini_cb, pattern=r"^laporan_hariini$"))
        app.add_handler(CallbackQueryHandler(laporan_bulanan_cb, pattern=r"^laporan_bulanan$"))
        app.add_handler(CallbackQueryHandler(cek_stok_cb,        pattern=r"^cek_stok$"))
        app.add_handler(CallbackQueryHandler(lunas_hutang,       pattern=r"^lunas_hutang_"))
        app.add_handler(CallbackQueryHandler(download_excel_cb,  pattern=r"^download_excel_"))
        app.add_handler(CallbackQueryHandler(confirm_nota, pattern=r"^confirm_[a-f0-9\-]{36}$"))
        app.add_handler(CallbackQueryHandler(edit_nota,    pattern=r"^edit_[a-f0-9\-]{36}$"))
        app.add_handler(CallbackQueryHandler(cancel_nota,  pattern=r"^cancel_[a-f0-9\-]{36}$"))
        app.add_handler(CallbackQueryHandler(edit_item,    pattern=r"^edit_item_"))
        app.add_handler(CallbackQueryHandler(selesai_kirim,    pattern=r"^selesai_kirim$"))
        app.add_handler(CallbackQueryHandler(konfirmasi_semua, pattern=r"^konfirmasi_semua_"))
        app.add_handler(CallbackQueryHandler(batal_semua,      pattern=r"^batal_semua_"))
        app.add_handler(CallbackQueryHandler(kirim_ulang,      pattern=r"^kirim_ulang_"))
        app.add_handler(CallbackQueryHandler(hubungkan_akun, pattern="^hubungkan_akun$"))
        app.add_handler(CallbackQueryHandler(buka_web,       pattern="^buka_web$"))
        app.add_error_handler(bot_error_handler)
        return app

    # run_polling harus dipanggil LANGSUNG dari sync context, bukan dari dalam coroutine
    loop = _asyncio.new_event_loop()
    _asyncio.set_event_loop(loop)
    try:
        app = loop.run_until_complete(_create_app())
        # Set bot commands
        async def _set_commands(a):
            from telegram import BotCommand
            cmds = [
                BotCommand("start",    "Login atau lihat menu utama"),
                BotCommand("serah",    "🍱 Konfirmasi penyerahan MBG"),
                BotCommand("menu",     "📅 Input menu mingguan"),
                BotCommand("belanja",  "📝 Input belanja manual"),
                BotCommand("hariini",  "📊 Ringkasan hari ini"),
                BotCommand("laporan",  "📈 Laporan bulan ini"),
                BotCommand("stok",     "📦 Status stok bahan"),
                BotCommand("piutang",  "💰 Tagihan MBG belum lunas"),
                BotCommand("hutang",   "💸 Hutang ke supplier"),
                BotCommand("settings", "Lihat pengaturan akun"),
                BotCommand("logout",   "Logout akun"),
                BotCommand("cancel",   "Batalkan proses yang sedang berjalan"),
            ]
            await a.bot.set_my_commands(cmds)
        loop.run_until_complete(_set_commands(app))
        logger.info("Bot starting... Press Ctrl+C to stop")
        # run_polling memanage event loop sendiri — panggil di luar asyncio.run()
        app.run_polling(allowed_updates=[], close_loop=False)
    except KeyboardInterrupt:
        logger.info("Bot stopped.")
    finally:
        loop.close()

