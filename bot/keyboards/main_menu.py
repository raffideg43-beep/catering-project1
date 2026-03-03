"""
Telegram keyboards untuk main menu dan navigasi.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_main_menu() -> InlineKeyboardMarkup:
    """
    Get main menu keyboard.

    Layout:
    [📷 Catat Belanja] [📝 Belanja Manual]
    [🍱 Konfirmasi Serah] [📅 Menu Minggu Ini]
    [📊 Ringkasan] [📦 Cek Stok]
    [⚙️ Pengaturan]
    """
    keyboard = [
        [
            InlineKeyboardButton("📷 Catat Belanja", callback_data="catat_belanja"),
            InlineKeyboardButton("📝 Belanja Manual", callback_data="belanja_manual"),
        ],
        [
            InlineKeyboardButton("🍱 Konfirmasi Serah", callback_data="konfirmasi_serah"),
            InlineKeyboardButton("📅 Menu Minggu", callback_data="menu_minggu"),
        ],
        [
            InlineKeyboardButton("📊 Ringkasan", callback_data="ringkasan"),
            InlineKeyboardButton("📦 Cek Stok", callback_data="cek_stok"),
        ],
        [
            InlineKeyboardButton("⚙️ Pengaturan", callback_data="pengaturan"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_back_button(callback_data: str = "back_main") -> InlineKeyboardMarkup:
    """Get back button to return to main menu."""
    keyboard = [[InlineKeyboardButton("← Kembali ke Menu", callback_data=callback_data)]]
    return InlineKeyboardMarkup(keyboard)


def get_login_menu() -> InlineKeyboardMarkup:
    """Get login menu for unauthenticated users."""
    keyboard = [[InlineKeyboardButton("🔗 Hubungkan Akun", callback_data="hubungkan_akun")]]
    return InlineKeyboardMarkup(keyboard)


def get_open_web_button() -> InlineKeyboardMarkup:
    """Get button to open web dashboard."""
    keyboard = [[InlineKeyboardButton("🌐 Buka Dashboard Web", callback_data="buka_web")]]
    return InlineKeyboardMarkup(keyboard)
