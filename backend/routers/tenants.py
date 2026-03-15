"""
Tenant management endpoints.
"""

import random
import string
from datetime import datetime, timedelta
from typing import Any, Dict
from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from core.database import get_supabase
from core.dependencies import get_current_user, require_role
from core.security import create_access_token
from core.config import settings
from models.tenant import TenantResponse, TenantUpdate
from models.user import UserInDB, UserResponse

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.get("/me", response_model=Dict[str, Any])
def get_current_tenant(current_user: UserInDB = Depends(get_current_user)):
    """Get current tenant info."""
    supabase = get_supabase()
    response = (
        supabase.table("tenants")
        .select("*")
        .eq("id", current_user.tenant_id)
        .single()
        .execute()
    )
    tenant_data = getattr(response, "data", None)
    if not tenant_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    # Ambil contact_name dari nama tabel users (owner)
    owner_query = supabase.table("users").select("name").eq("tenant_id", current_user.tenant_id).eq("role", "owner").limit(1).execute()
    owners = getattr(owner_query, "data", None)
    if owners:
        tenant_data["contact_name"] = owners[0].get("name")

    return {"success": True, "data": TenantResponse(**tenant_data)}


@router.put("/me", response_model=Dict[str, Any], dependencies=[Depends(require_role(["owner"]))])
def update_tenant(
    body: TenantUpdate,
    current_user: UserInDB = Depends(get_current_user),
):
    """Update current tenant info."""
    supabase = get_supabase()

    update_data = {}
    if body.name is not None:
        update_data["name"] = body.name
    if body.phone is not None:
        update_data["phone"] = body.phone
    if body.address is not None:
        update_data["address"] = body.address
    if body.business_type is not None:
        update_data["business_type"] = body.business_type
    if body.sppg_code is not None:
        update_data["sppg_code"] = body.sppg_code
    
    if body.contact_name is not None:
        # Field "contact_name" tidak ada di tabel tenants. 
        # Simpan nama pemilik ke master tabel users supaya UI tidak kehilangan datanya
        user_update = supabase.table("users").update({"name": body.contact_name}).eq("tenant_id", current_user.tenant_id).eq("role", "owner").execute()

    # Hanya jalankan update di tabel tenants KETIKA ada field selain contact_name
    tenant_list = []
    if update_data:
        response = (
            supabase.table("tenants")
            .update(update_data)
            .eq("id", current_user.tenant_id)
            .execute()
        )
        tenant_list = getattr(response, "data", None) or []
    else:
        # Panggil ulang datanya saja tanpa update ke tabel tenants karena kosong
        response = supabase.table("tenants").select("*").eq("id", current_user.tenant_id).execute()
        tenant_list = getattr(response, "data", None) or []

    if not tenant_list:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update tenant",
        )

    # Sisipkan contact_name di response akhir
    tenant_resp = tenant_list[0]
    if body.contact_name is not None:
        tenant_resp["contact_name"] = body.contact_name
    elif current_user:
        # Ambil kembali the latest name kalau nggak disubmit tp ada di db users
        owner_query = supabase.table("users").select("name").eq("tenant_id", current_user.tenant_id).eq("role", "owner").limit(1).execute()
        owners = getattr(owner_query, "data", None)
        if owners:
            tenant_resp["contact_name"] = owners[0].get("name")

    return {"success": True, "data": TenantResponse(**tenant_resp)}


@router.post("/telegram-link-code", response_model=Dict[str, Any], dependencies=[Depends(require_role(["owner"]))])
def generate_telegram_link_code(current_user: UserInDB = Depends(get_current_user)):
    """Generate linking code untuk Telegram."""
    supabase = get_supabase()

    # Generate kode unik 6 karakter
    code = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    expires_at = datetime.utcnow() + timedelta(minutes=10)

    # Simpan ke session_token user
    supabase.table("users").update({"session_token": code}).eq("id", current_user.id).execute()

    return {
        "success": True,
        "data": {
            "code": code,
            "expires_at": expires_at.isoformat(),
        },
    }


class TelegramLinkRequest(BaseModel):
    telegram_id: int
    linking_code: str


@router.post("/telegram-link", response_model=Dict[str, Any])
def link_telegram_account(body: TelegramLinkRequest):
    """Link Telegram account dengan kode yang digenerate."""
    telegram_id = body.telegram_id
    linking_code = body.linking_code

    if not telegram_id or not linking_code:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "error": "telegram_id and linking_code required"},
        )

    supabase = get_supabase()

    # Cari user dengan kode ini
    response = supabase.table("users").select("*").eq("session_token", linking_code).execute()
    users = getattr(response, "data", None) or []

    if not users:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"success": False, "error": "Kode tidak valid atau sudah expired"},
        )

    user_row = users[0]

    # Update telegram_id dan clear session_token
    supabase.table("users").update(
        {"telegram_id": telegram_id, "session_token": None}
    ).eq("id", user_row["id"]).execute()

    # Generate token untuk bot
    token = create_access_token(
        data={
            "user_id": user_row["id"],
            "tenant_id": user_row["tenant_id"],
        }
    )

    user_resp = UserResponse(
        id=user_row["id"],
        name=user_row["name"],
        email=user_row["email"],
        role=user_row["role"],
        tenant_id=user_row["tenant_id"],
    )

    return {
        "success": True,
        "data": {
            "access_token": token,
            "user": user_resp,
        },
    }
