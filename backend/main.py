import logging
from typing import Any, Dict

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings, validate_config
from core.dependencies import get_current_user, require_role
from core.error_handlers import register_error_handlers
from core.health import health_router
from middleware.logging import RequestLoggingMiddleware
from models.user import UserInDB
from routers import auth as auth_router
from routers import tenants as tenants_router
from routers import schools as schools_router
from routers import suppliers as suppliers_router
from routers import products as products_router
from routers import recipes as recipes_router
from routers import mbg_settings as mbg_settings_router
from routers import mbg as mbg_router
from routers.mbg import delivery_router as mbg_delivery_router
from routers import transactions as transactions_router
from routers import reports as reports_router
from routers import payables as payables_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="MBG Catering Backend", version="1.0.0")


# ─── CORS ──────────────────────────────────────────────────────────────────
if settings.app_env == "development":
    origins = ["*"]
else:
    origins = [
        o for o in [settings.web_url, settings.backend_url,
                    "http://localhost:3000", "http://localhost:8000"]
        if o
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RequestLoggingMiddleware)

# ─── Error Handlers ─────────────────────────────────────────────────────────
register_error_handlers(app)

# ─── Routers ─────────────────────────────────────────────────────────────────
app.include_router(health_router)


@app.on_event("startup")
async def startup_event():
    """Startup: validate config dan log info."""
    try:
        validate_config()
    except ValueError as e:
        logger.warning("Config validation (non-fatal in dev): %s", e)
    logger.info("Backend started — env: %s", settings.app_env)


@app.get("/")
def root():
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
app.include_router(tenants_router.router)
app.include_router(schools_router.router)
app.include_router(suppliers_router.router)
app.include_router(products_router.router)
app.include_router(recipes_router.router)
app.include_router(mbg_settings_router.router)
app.include_router(mbg_router.router, prefix="/mbg")
app.include_router(mbg_delivery_router, prefix="/mbg")
app.include_router(transactions_router.router, prefix="/transactions")
app.include_router(reports_router.router)
app.include_router(payables_router.router)












