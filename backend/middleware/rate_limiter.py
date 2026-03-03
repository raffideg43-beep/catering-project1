"""
Rate limiter middleware untuk FastAPI.
Menggunakan Redis untuk tracking jumlah request per user per action.
"""

import redis
from fastapi import Depends, HTTPException, Request, status

from core.config import settings
from core.dependencies import get_current_user
from models.user import UserInDB

# Redis connection pool
_redis_client: redis.Redis | None = None


def get_redis_client() -> redis.Redis:
    """
    Return a singleton Redis client.
    """
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


class RateLimiter:
    """
    Rate limiter dependency untuk FastAPI endpoints.

    Args:
        action: Identifier aksi (misal: "photo_upload", "login")
        limit: Maximum request dalam window (misal: 10)
        window: Durasi window dalam detik (misal: 60)

    Usage:
        photo_upload_limiter = RateLimiter("photo_upload", 10, 60)

        @router.post("/upload", dependencies=[Depends(photo_upload_limiter)])
        def upload_photo(...):
            pass
    """

    def __init__(self, action: str, limit: int, window: int):
        self.action = action
        self.limit = limit
        self.window = window

    async def __call__(
        self,
        request: Request,
        current_user: UserInDB = Depends(get_current_user),
    ) -> None:
        """
        Validate rate limit. Raise HTTP 429 jika limit terlampaui.
        """
        redis_client = get_redis_client()
        key = f"rate:{current_user.id}:{self.action}"

        try:
            count = redis_client.incr(key)
            if count == 1:
                redis_client.expire(key, self.window)

            if count > self.limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "success": False,
                        "error": f"Terlalu banyak request. Coba lagi dalam {self.window} detik.",
                    },
                )
        except redis.RedisError as e:
            # Log error tapi tetap izinkan request jika Redis fail
            print(f"Redis error during rate limiting: {e}")


# ─── Instance siap pakai ───

photo_upload_limiter = RateLimiter(
    action="photo_upload",
    limit=settings.photo_rate_limit_per_user,
    window=settings.photo_rate_limit_window_seconds,
)

login_limiter = RateLimiter(
    action="login",
    limit=5,
    window=300,  # 5 menit
)

api_limiter = RateLimiter(
    action="api_general",
    limit=100,
    window=60,  # 100 request per menit
)
