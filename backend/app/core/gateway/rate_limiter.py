import logging
from datetime import date

logger = logging.getLogger(__name__)

_TTL_SECONDS = 86400  # 24 часа


class RateLimiter:
    """Счётчик запросов на юзера в сутки. Ключ ratelimit:{user_id}:{YYYY-MM-DD},
    INCR + EXPIRE(24ч). Redis недоступен → fail-open (пропускаем, логируем WARN)."""

    def __init__(self, redis_client, limit_per_day: int):
        self.redis = redis_client
        self.limit = limit_per_day

    async def is_allowed(self, user_id: str, today: date | None = None) -> bool:
        day = (today or date.today()).isoformat()
        key = f"ratelimit:{user_id}:{day}"
        try:
            count = await self.redis.incr(key)
            if count == 1:
                await self.redis.expire(key, _TTL_SECONDS)
            return count <= self.limit
        except Exception as exc:
            logger.warning("rate-limit Redis error → fail-open: %s", exc)
            return True
