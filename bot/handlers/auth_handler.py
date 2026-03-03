"""
Telegram auth handlers: /start, /logout, /settings, etc.
"""

import logging
from functools import wraps
from typing import Callable

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from core.config import settings  # type: ignore[assignment]
from keyboards.main_menu import (
    get_login_menu,
    get_main_menu,
    get_open_web_button,
)
from utils.api_client import APIClient, get_api_client
from utils.formatter import format_error, format_success
from utils.session import (
    clear_session,
    get_token,
    get_user_name,
    is_authenticated,
    save_session,
)

logger = logging.getLogger(__name__)


def require_auth(func: Callable) -> Callable:
    """
    Decorator untuk mengecek autentikasi user.
    Jika belum auth, reply "Silakan /start dulu" dan return.
    """

    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
        if not is_authenticated(context):
            if update.message:
                await update.message.reply_text(
                    "❌ Silakan /start dulu untuk login.",
                    reply_markup=get_login_menu(),
                )
            return ConversationHandler.END
        return await func(update, context)

    return wrapper


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler untuk /start command.
    Jika dengan argumen (kode): hubungkan akun langsung.
    Jika tanpa argumen: tampilkan pesan sambutan.
    """
    if not update.message:
        return

    api_client = get_api_client(settings.backend_url)  # type: ignore[attr-defined]

    # Cek apakah sudah authenticated
    if is_authenticated(context):
        try:
            token = get_token(context)
            response = await api_client.get("/auth/me", token=token)
            user_data = response.get("data", {}).get("user", {})
            user_name = user_data.get("name", "User")

            await update.message.reply_text(
                f"👋 Selamat datang kembali, {user_name}!\n\n"
                f"Role: {user_data.get('role', 'Unknown')}\n\n"
                "Apa yang ingin kamu lakukan?",
                reply_markup=get_main_menu(),
            )
            return
        except Exception as e:
            # Token expired, clear session
            logger.warning(f"Token invalid: {e}")
            await clear_session(context)

    # Cek apakah ada argumen (kode linking)
    if context.args and len(context.args) > 0 and update.effective_user:
        linking_code = context.args[0]
        try:
            response = await api_client.post(
                "/auth/telegram-link",
                data={
                    "telegram_id": update.effective_user.id,
                    "linking_code": linking_code,
                },
            )
            if response.get("success"):
                data = response.get("data", {})
                user = data.get("user", {})
                token = data.get("access_token", "")

                await save_session(
                    context,
                    token=token,
                    tenant_id=user.get("tenant_id", ""),
                    user_name=user.get("name", ""),
                    user_role=user.get("role", ""),
                )

                await update.message.reply_text(
                    f"{format_success('Akun berhasil dihubungkan!')}\n\n"
                    f"Selamat datang, {user.get('name')}! 🎉",
                    reply_markup=get_main_menu(),
                )
                return
            else:
                error_msg = response.get("error", "Kode tidak valid")
                await update.message.reply_text(
                    f"{format_error(error_msg)}\n\n"
                    f"Minta kode baru di:\n"
                    f"{settings.web_url}/settings/telegram",  # type: ignore[attr-defined]
                )
                return
        except Exception as e:
            logger.error(f"Linking error: {e}")
            await update.message.reply_text(
                f"{format_error(str(e))}\n\n"
                f"Minta kode baru di:\n"
                f"{settings.web_url}/settings/telegram",  # type: ignore[attr-defined]
            )
            return

    # Belum auth, tampilkan sambutan
    await update.message.reply_text(
        "👋 Halo! Saya asisten SPPG Anda.\n\n"
        "Untuk mulai, hubungkan akun terlebih dahulu.\n\n"
        "❓ Belum punya akun?\n"
        f"📝 Daftar di: {settings.web_url}/register\n\n"  # type: ignore[attr-defined]
        "✔️ Sudah punya akun?\n"
        "Klik tombol di bawah atau ikuti instruksi.",
        reply_markup=get_login_menu(),
    )


async def hubungkan_akun(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler callback untuk tombol 'Hubungkan Akun'.
    Tampilkan instruksi step-by-step.
    """
    query = update.callback_query
    if not query:
        return
    await query.answer()

    await query.edit_message_text(
        "🔗 Cara Hubungkan Akun:\n\n"
        "1️⃣ Buka browser dan masuk ke:\n"
        f"   {settings.web_url}\n\n"  # type: ignore[attr-defined]
        "2️⃣ Login atau daftar akun baru\n\n"
        "3️⃣ Pergi ke: Pengaturan → Telegram\n\n"
        "4️⃣ Klik 'Generate Kode Telegram'\n\n"
        "5️⃣ Copy kode yang muncul\n\n"
        "6️⃣ Ketik di sini: /start [kode]\n\n"
        "Contoh: /start ABC123XYZ\n\n"
        "Jika sudah, tinggal ketik command di atas!",
        reply_markup=get_login_menu(),
    )


async def logout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler untuk /logout command.
    """
    if not update.message:
        return

    if not is_authenticated(context):
        await update.message.reply_text(
            "❌ Kamu belum login. Ketik /start untuk login.",
        )
        return

    api_client = get_api_client(settings.backend_url)  # type: ignore[attr-defined]
    token = get_token(context)

    try:
        await api_client.post("/auth/logout", token=token)
    except Exception as e:
        logger.warning(f"Logout error (ignored): {e}")

    await clear_session(context)
    await update.message.reply_text(
        f"{format_success('Berhasil logout.')}\n\n"
        "Sampai jumpa! 👋\n"
        "Ketik /start untuk login kembali.",
    )


@require_auth
async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler untuk /settings command.
    Tampilkan informasi akun user.
    """
    if not update.message:
        return

    api_client = get_api_client(settings.backend_url)  # type: ignore[attr-defined]
    token = get_token(context)

    try:
        response = await api_client.get("/auth/me", token=token)
        data = response.get("data", {})
        user = data.get("user", {})
        tenant = data.get("tenant", {})

        message = (
            "⚙️ Pengaturan Akun\n\n"
            f"👤 Nama: {user.get('name', 'N/A')}\n"
            f"📧 Email: {user.get('email', 'N/A')}\n"
            f"🏢 SPPG: {tenant.get('name', 'N/A')}\n"
            f"🔑 Role: {user.get('role', 'N/A')}\n\n"
            "Untuk setup lengkap (sekolah, supplier, BOM):\n"
            f"🌐 {settings.web_url}/settings"  # type: ignore[attr-defined]
        )

        await update.message.reply_text(
            message,
            reply_markup=get_open_web_button(),
        )
    except Exception as e:
        logger.error(f"Settings error: {e}")
        await update.message.reply_text(
            f"{format_error(f'Tidak bisa load settings: {str(e)}')}",
        )


async def buka_web(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler callback untuk tombol 'Buka Dashboard Web'.
    """
    query = update.callback_query
    if not query:
        return
    await query.answer()

    await query.edit_message_text(
        "🌐 Buka dashboard di browser:\n\n"
        f"👉 {settings.web_url}\n\n"  # type: ignore[attr-defined]
        "💡 Simpan link ini di bookmark\n"
        "untuk akses cepat berikutnya.",
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler global untuk error.
    """
    logger.error(f"Exception while handling an update: {context.error}")

    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                f"{format_error('Terjadi kesalahan.')}\n\n"
                "Coba lagi atau ketik /start untuk mulai ulang.",
            )
        except Exception as e:
            logger.error(f"Error sending error message: {e}")
