import os
from pathlib import Path
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve path .env secara absolut dari lokasi config.py ini
# config.py ada di backend/core/ → naik 1 level ke backend/
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    # --- Supabase ---
    supabase_url: str = ""
    supabase_service_key: str = ""
    supabase_anon_key: str | None = None

    # --- Auth / JWT ---
    secret_key: str = "dev-secret-key-ganti-di-production"
    access_token_expire_minutes: int = 1440
    algorithm: str = "HS256"

    # --- Telegram ---
    telegram_bot_token: str | None = None

    # --- AI ---
    gemini_api_key: str | None = None
    gemini_ocr_model: str = "gemini-2.5-flash"
    gemini_text_model: str = "gemini-2.5-flash-lite"

    # --- Redis ---
    redis_url: str = "redis://localhost:6379"

    # --- App ---
    app_env: str = "development"
    backend_url: str = "http://localhost:8000"
    web_url: str = "http://localhost:3000"

    # --- Rate limiting ---
    photo_rate_limit_per_user: int = 10
    photo_rate_limit_window_seconds: int = 60

    # --- MBG settings (sesuai MASTER_PLAN v1.7) ---
    mbg_price_per_portion: int = 15000
    mbg_pph22_rate: float = 0.015
    mbg_ppn_rate: float = 0.11
    mbg_food_allocation: float = 0.80
    mbg_labor_allocation: float = 0.15
    mbg_ops_allocation: float = 0.05

    # --- OCR / Worker ---
    ocr_worker_count: int = 2
    ocr_job_timeout: int = 120

    model_config = SettingsConfigDict(
        # Path absolut — tidak bergantung dari mana uvicorn dijalankan
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


def validate_config() -> None:
    """
    Validasi semua ENV vars wajib saat startup.
    Raise ValueError jika ada yang tidak terisi.
    """
    required_map = {
        "SUPABASE_URL":        settings.supabase_url,
        "SUPABASE_SERVICE_KEY": settings.supabase_service_key,
        "SECRET_KEY":          settings.secret_key,
        "TELEGRAM_BOT_TOKEN":  settings.telegram_bot_token,
        "GEMINI_API_KEY":      settings.gemini_api_key,
        "REDIS_URL":           settings.redis_url,
    }

    missing = [k for k, v in required_map.items() if not v]

    if missing:
        raise ValueError(
            f"❌ ENV vars wajib tidak ada: {', '.join(missing)}\n"
            "Periksa file .env Anda."
        )
