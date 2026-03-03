from typing import Any, Dict

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.dependencies import get_current_user, require_role
from models.user import UserInDB
from routers import auth as auth_router

app = FastAPI(title="MBG Catering Backend", version="1.0.0")

origins = [
    settings.web_url,
    "http://localhost:3000",
    "https://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in origins if o],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def health_check():
    # Mengikuti spesifikasi modul: response sederhana tanpa wrapper.
    return {"status": "ok", "version": "1.0.0"}


# ─── Test endpoint untuk verifikasi role checking (Modul 3) ───
@app.get(
    "/test-role-owner",
    dependencies=[Depends(require_role(["owner"]))],
    response_model=Dict[str, Any],
)
def test_role_owner(current_user: UserInDB = Depends(get_current_user)):
    """
    Test endpoint: hanya owner yang bisa akses.
    Jalankan test setelah server start, kemudian hapus endpoint ini.
    """
    return {
        "success": True,
        "message": f"Halo {current_user.name}, kamu owner",
        "role": current_user.role,
    }


@app.get(
    "/test-role-kasir",
    dependencies=[Depends(require_role(["owner", "admin", "kasir"]))],
    response_model=Dict[str, Any],
)
def test_role_kasir(current_user: UserInDB = Depends(get_current_user)):
    """
    Test endpoint: owner, admin, dan kasir bisa akses.
    Jalankan test setelah server start, kemudian hapus endpoint ini.
    """
    return {
        "success": True,
        "message": f"Halo {current_user.name}, kamu bisa input",
        "role": current_user.role,
    }


# ─── End of test endpoints ───

app.include_router(auth_router.router)





