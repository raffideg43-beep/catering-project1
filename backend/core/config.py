from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Supabase
    supabase_url: str
    supabase_service_key: str
    supabase_anon_key: str | None = None

    # Auth / JWT
    secret_key: str
    access_token_expire_minutes: int = 1440
    algorithm: str = "HS256"

    # Telegram
    telegram_bot_token: str | None = None

    # AI
    gemini_api_key: str | None = None

    # Redis
    redis_url: str

    # App
    app_env: str = "development"
    backend_url: str
    web_url: str

    # Rate limiting
    photo_rate_limit_per_user: int = 10
    photo_rate_limit_window_seconds: int = 60

    # MBG settings (defaults diambil dari MASTER_PLAN, bisa dioverride ENV)
    mbg_price_per_portion: int = 15000
    mbg_pph22_rate: float = 0.015
    mbg_ppn_rate: float = 0.11
    mbg_food_allocation: float = 0.80
    mbg_labor_allocation: float = 0.15
    mbg_ops_allocation: float = 0.05

    # OCR / Worker
    ocr_worker_count: int = 2
    ocr_job_timeout: int = 120

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()












