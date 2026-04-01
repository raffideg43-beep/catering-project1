"""
Telegram keyboards untuk main menu dan navigasi.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_main_menu(role: str = "") -> InlineKeyboardMarkup:
    """
    Main menu keyboard dengan Role-Based Access Control (RBAC).
    """
    role = (role or "").lower()
    keyboard = []

    # 1. Baris Operasional (Catat Nota - Belanja Manual)
    # Boleh diakses oleh: owner, admin, kasir
    row_1 = []
    if role in ["owner", "admin", "kasir"]:
        row_1.append(InlineKeyboardButton("📷 Catat Nota", callback_data="catat_belanja"))
        row_1.append(InlineKeyboardButton("📝 Belanja Manual", callback_data="belanja"))
    if row_1:
        keyboard.append(row_1)

    # 2. Baris Pengiriman (Konfirmasi Serah - Menu Minggu)
    # Konfirmasi Serah: owner, admin, kasir, driver
    # Menu Minggu: owner, admin
    row_2 = []
    if role in ["owner", "admin", "kasir", "driver"]:
        row_2.append(InlineKeyboardButton("🍱 Konfirmasi Serah", callback_data="serah"))
    if role in ["owner", "admin"]:
        row_2.append(InlineKeyboardButton("📅 Menu Minggu", callback_data="menu_minggu"))
    if row_2:
        keyboard.append(row_2)

    # 3. Baris Laporan (Laporan Hari Ini - Laporan Bulanan)
    # Boleh diakses oleh: owner, admin, viewer
    row_3 = []
    if role in ["owner", "admin", "viewer"]:
        row_3.append(InlineKeyboardButton("📊 Laporan Hari Ini", callback_data="laporan_hariini"))
        row_3.append(InlineKeyboardButton("📈 Laporan Bulanan", callback_data="laporan_bulanan"))
    if row_3:
        keyboard.append(row_3)

    # 4. Baris Utility (Cek Stok - Pengaturan)
    # Cek Stok: owner, admin, kasir, viewer
    # Pengaturan: owner, admin
    row_4 = []
    if role in ["owner", "admin", "kasir", "viewer"]:
        row_4.append(InlineKeyboardButton("📦 Cek Stok", callback_data="cek_stok"))
    if role in ["owner", "admin"]:
        row_4.append(InlineKeyboardButton("⚙️ Pengaturan", callback_data="pengaturan"))
    if row_4:
        keyboard.append(row_4)

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
