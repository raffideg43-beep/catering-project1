from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class BotSettings(BaseSettings):
    """Konfigurasi Telegram Bot."""

    telegram_bot_token: str
    backend_url: str
    web_url: str

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> BotSettings:
    return BotSettings()  # type: ignore[call-arg]


settings = get_settings()
