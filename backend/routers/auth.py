from datetime import timedelta
from typing import Any, Dict
from pydantic import BaseModel

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from core.config import settings
from core.database import get_supabase
from core.dependencies import get_current_user
from core.security import create_access_token, get_password_hash, verify_password
from middleware.rate_limiter import login_limiter
from models.user import LoginRequest, TokenResponse, UserCreate, UserInDB, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


def _build_success(data: Any) -> Dict[str, Any]:
    return {"success": True, "data": data}


def _build_error(message: str) -> Dict[str, Any]:
    return {"success": False, "error": message}


@router.post("/register-tenant", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
def register_tenant(body: Dict[str, Any]):
    """
    Register tenant baru + owner user pertama.
    Body: tenant_name, slug, owner_email, password, phone
    """
    required_fields = {"tenant_name", "slug", "owner_email", "password", "phone"}
    if not required_fields.issubset(body.keys()):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=_build_error("Missing required fields"),
        )

    tenant_name = body["tenant_name"]
    slug = body["slug"]
    owner_email = body["owner_email"]
    password = body["password"]
    phone = body["phone"]

    supabase = get_supabase()

    # Validasi slug unik
    existing_tenant = supabase.table("tenants").select("id").eq("slug", slug).execute()
    if getattr(existing_tenant, "data", None):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=_build_error("Slug already in use"),
        )

    # Validasi email unik
    existing_user = supabase.table("users").select("id").eq("email", owner_email).execute()
    if getattr(existing_user, "data", None):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=_build_error("Email already in use"),
        )

    # Insert tenant
    tenant_insert = (
        supabase.table("tenants")
        .insert(
            {
                "name": tenant_name,
                "slug": slug,
                "owner_email": owner_email,
                "phone": phone,
            }
        )
        .execute()
    )
    tenant_data_list = getattr(tenant_insert, "data", None) or []
    if not tenant_data_list:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_build_error("Failed to create tenant"),
        )
    tenant = tenant_data_list[0]
    tenant_id = tenant["id"]

    # Insert owner user
    hashed_password = get_password_hash(password)
    user_insert = (
        supabase.table("users")
        .insert(
            {
                "tenant_id": tenant_id,
                "email": owner_email,
                "name": tenant_name,
                "role": "owner",
                "password_hash": hashed_password,
                "is_active": True,
            }
        )
        .execute()
    )
    user_data_list = getattr(user_insert, "data", None) or []
    if not user_data_list:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_build_error("Failed to create owner user"),
        )
    user_row = user_data_list[0]

    user_resp = UserResponse(
        id=user_row["id"],
        name=user_row["name"],
        email=user_row["email"],
        role=user_row["role"],
        tenant_id=user_row["tenant_id"],
    )


    token = create_access_token(
        data={"user_id": user_resp.id, "tenant_id": user_resp.tenant_id}
    )
    token_response = TokenResponse(access_token=token, user=user_resp)

    return _build_success(token_response.dict())


@router.post("/login", response_model=Dict[str, Any], dependencies=[Depends(login_limiter)])
def login(body: LoginRequest):
    supabase = get_supabase()
    result = supabase.table("users").select("*").eq("email", body.email).execute()
    users = getattr(result, "data", None) or []
    if not users:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content=_build_error("Invalid email or password"),
        )

    user_row = users[0]
    password_hash = user_row.get("password_hash") or ""
    if not password_hash or not verify_password(body.password, password_hash):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content=_build_error("Invalid email or password"),
        )

    user_resp = UserResponse(
        id=user_row["id"],
        name=user_row["name"],
        email=user_row["email"],
        role=user_row["role"],
        tenant_id=user_row["tenant_id"],
    )

    token = create_access_token(
        data={"user_id": user_resp.id, "tenant_id": user_resp.tenant_id}
    )
    token_response = TokenResponse(access_token=token, user=user_resp)

    return _build_success(token_response.dict())


class TelegramLoginRequest(BaseModel):
    telegram_id: int
    session_token: str

@router.post("/telegram-login", response_model=Dict[str, Any])
def telegram_login(body: TelegramLoginRequest):
    """
    Login via Telegram: body harus berisi telegram_id (int) dan session_token (str).
    """
    telegram_id = body.telegram_id
    session_token = body.session_token
    if telegram_id is None or session_token is None:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=_build_error("telegram_id and session_token are required"),
        )

    supabase = get_supabase()
    result = (
        supabase.table("users")
        .select("*")
        .eq("telegram_id", telegram_id)
        .eq("session_token", session_token)
        .execute()
    )
    users = getattr(result, "data", None) or []
    if not users:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content=_build_error("Invalid Telegram session"),
        )

    user_row = users[0]
    if not user_row.get("is_active", True):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content=_build_error("User is inactive"),
        )

    user_resp = UserResponse(
        id=user_row["id"],
        name=user_row["name"],
        email=user_row["email"],
        role=user_row["role"],
        tenant_id=user_row["tenant_id"],
    )

    token = create_access_token(
        data={"user_id": user_resp.id, "tenant_id": user_resp.tenant_id}
    )
    token_response = TokenResponse(access_token=token, user=user_resp)

    return _build_success(token_response.dict())


@router.post("/refresh", response_model=Dict[str, Any])
def refresh_token(current_user: UserInDB = Depends(get_current_user)):
    token = create_access_token(
        data={"user_id": current_user.id, "tenant_id": current_user.tenant_id}
    )
    user_resp = UserResponse(
        id=current_user.id,
        name=current_user.name,
        email=current_user.email,
        role=current_user.role,
        tenant_id=current_user.tenant_id,
    )
    token_response = TokenResponse(access_token=token, user=user_resp)
    return _build_success(token_response.dict())


@router.post("/logout", response_model=Dict[str, Any])
def logout(current_user: UserInDB = Depends(get_current_user)):
    supabase = get_supabase()
    supabase.table("users").update({"session_token": None}).eq("id", current_user.id).execute()
    return {"success": True, "message": "Logged out"}


@router.get("/me", response_model=Dict[str, Any])
def get_me(current_user: UserInDB = Depends(get_current_user)):
    supabase = get_supabase()
    tenant_res = (
        supabase.table("tenants")
        .select("id,name,slug,plan")
        .eq("id", current_user.tenant_id)
        .execute()
    )
    tenant_list = getattr(tenant_res, "data", None) or []
    tenant = tenant_list[0] if tenant_list else None

    user_resp = UserResponse(
        id=current_user.id,
        name=current_user.name,
        email=current_user.email,
        role=current_user.role,
        tenant_id=current_user.tenant_id,
    )

    return _build_success(
        {
            "user": user_resp.dict(),
            "tenant": tenant,
        }
    )



















