"""
Helper untuk manage session context.user_data di Telegram.
"""

from telegram.ext import ContextTypes


async def save_session(
    context: ContextTypes.DEFAULT_TYPE,
    token: str,
    tenant_id: str,
    user_name: str,
    user_role: str,
) -> None:
    """Simpan session token & user info ke context."""
    context.user_data["token"] = token
    context.user_data["tenant_id"] = tenant_id
    context.user_data["user_name"] = user_name
    context.user_data["user_role"] = user_role


async def clear_session(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Hapus semua session dari context."""
    context.user_data.pop("token", None)
    context.user_data.pop("tenant_id", None)
    context.user_data.pop("user_name", None)
    context.user_data.pop("user_role", None)


def is_authenticated(context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Return True jika user sudah authenticated (punya token)."""
    token = context.user_data.get("token")
    return token is not None and len(token) > 0


def get_token(context: ContextTypes.DEFAULT_TYPE) -> str | None:
    """Return token atau None."""
    return context.user_data.get("token")


def get_role(context: ContextTypes.DEFAULT_TYPE) -> str | None:
    """Return role atau None."""
    return context.user_data.get("user_role")


def get_user_name(context: ContextTypes.DEFAULT_TYPE) -> str | None:
    """Return user name atau None."""
    return context.user_data.get("user_name")


def can_input(context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Return True jika user bisa input (owner, admin, kasir)."""
    role = get_role(context)
    return role in ["owner", "admin", "kasir"]
