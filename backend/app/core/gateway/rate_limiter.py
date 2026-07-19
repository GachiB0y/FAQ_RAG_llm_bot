import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta

logger = logging.getLogger(__name__)

_TTL_SECONDS = 86400  # 24 часа


@dataclass
class RateLimitStatus:
    allowed: bool
    remaining: int
    limit: int
    reset_seconds: int


def _seconds_until_midnight(now: datetime | None = None) -> int:
    now = now or datetime.now()
    tomorrow = (now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return int((tomorrow - now).total_seconds())


class RateLimiter:
    """Счётчик запросов на юзера в сутки. Ключ ratelimit:{user_id}:{YYYY-MM-DD},
    INCR + EXPIRE(24ч). Redis недоступен → fail-open (пропускаем, логируем WARN).
    Сброс — в полночь сервера (ключ датовый)."""

    def __init__(self, redis_client, limit_per_day: int):
        self.redis = redis_client
        self.limit = limit_per_day

    async def hit(
        self, user_id: str, today: date | None = None, now: datetime | None = None
    ) -> RateLimitStatus:
        day = (today or date.today()).isoformat()
        key = f"ratelimit:{user_id}:{day}"
        reset = _seconds_until_midnight(now)
        try:
            count = await self.redis.incr(key)
            if count == 1:
                await self.redis.expire(key, _TTL_SECONDS)
        except Exception as exc:
            logger.warning("rate-limit Redis error → fail-open: %s", exc)
            return RateLimitStatus(True, self.limit, self.limit, reset)
        remaining = max(0, self.limit - count)
        return RateLimitStatus(count <= self.limit, remaining, self.limit, reset)

    async def is_allowed(self, user_id: str, today: date | None = None) -> bool:
        return (await self.hit(user_id, today)).allowed
