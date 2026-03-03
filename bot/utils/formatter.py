"""
Utility formatters untuk display pesan di Telegram.
"""

from datetime import datetime


def format_currency(amount: int | float) -> str:
    """
    Format uang ke format Indonesia.
    1500000 → "Rp 1.500.000"
    """
    if isinstance(amount, float):
        amount = int(amount)
    formatted = f"{amount:,}".replace(",", ".")
    return f"Rp {formatted}"


def format_date(date_str: str) -> str:
    """
    Format tanggal dari YYYY-MM-DD ke format Indonesia.
    "2025-01-15" → "Rabu, 15 Jan 2025"
    """
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        day_names = [
            "Senin",
            "Selasa",
            "Rabu",
            "Kamis",
            "Jumat",
            "Sabtu",
            "Minggu",
        ]
        day_name = day_names[date_obj.weekday()]
        formatted = date_obj.strftime("%d %b %Y")
        return f"{day_name}, {formatted}"
    except (ValueError, IndexError):
        return date_str


def format_success(msg: str) -> str:
    """Bungkus pesan dengan emoji sukses."""
    return f"✅ {msg}"


def format_error(msg: str) -> str:
    """Bungkus pesan dengan emoji error."""
    return f"❌ {msg}"


def format_warning(msg: str) -> str:
    """Bungkus pesan dengan emoji warning."""
    return f"⚠️ {msg}"


def format_info(msg: str) -> str:
    """Bungkus pesan dengan emoji informasi."""
    return f"ℹ️ {msg}"


def truncate(text: str, max_len: int = 50) -> str:
    """
    Potong teks jika terlalu panjang + tambahkan "..."
    """
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text
