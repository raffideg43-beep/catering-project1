"""
Telegram keyboards untuk main menu dan navigasi.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_main_menu() -> InlineKeyboardMarkup:
    """
    Main menu keyboard — Modul 11 update.

    Layout:
    [📷 Catat Nota] [📝 Belanja Manual]
    [🍱 Konfirmasi Serah] [📅 Menu Minggu]
    [📊 Laporan Hari Ini] [📈 Laporan Bulanan]
    [📦 Cek Stok] [⚙️ Pengaturan]
    """
    keyboard = [
        [
            InlineKeyboardButton("📷 Catat Nota",     callback_data="catat_belanja"),
            InlineKeyboardButton("📝 Belanja Manual", callback_data="belanja"),
        ],
        [
            InlineKeyboardButton("🍱 Konfirmasi Serah", callback_data="serah"),
            InlineKeyboardButton("📅 Menu Minggu",      callback_data="menu_minggu"),
        ],
        [
            InlineKeyboardButton("📊 Laporan Hari Ini",  callback_data="laporan_hariini"),
            InlineKeyboardButton("📈 Laporan Bulanan",   callback_data="laporan_bulanan"),
        ],
        [
            InlineKeyboardButton("📦 Cek Stok",   callback_data="cek_stok"),
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
