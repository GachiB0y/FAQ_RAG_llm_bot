import logging
from uuid import uuid4

from .decision import GatewayDecision

logger = logging.getLogger(__name__)

_STATS_KEY = "gateway:stats"
_BYPASS_TRUTHY = {"1", "true", "yes", "on"}


def gateway_applies(enabled: bool, user_role: str, bypass_header: str | None) -> bool:
    """Нужно ли прогонять gateway.check для этого запроса.
    - enabled=False (мастер-выключатель) → не применяем.
    - admin + truthy bypass-заголовок → не применяем (лайв-тест из админки).
    - иначе (в т.ч. бот, чей заголовок игнорируется — он не admin) → применяем."""
    if not enabled:
        return False
    if user_role == "admin" and (bypass_header or "").strip().lower() in _BYPASS_TRUTHY:
        return False
    return True


class SecurityGateway:
    """Единый шлюз перед RAGEngine.query. Порядок: rate-limit → injection."""

    def __init__(self, rate_limiter, injection_guard, redis_client):
        self.rate_limiter = rate_limiter
        self.injection = injection_guard
        self.redis = redis_client

    async def check(self, user_id: str, text: str) -> GatewayDecision:
        trace_id = str(uuid4())

        status = await self.rate_limiter.hit(user_id)
        if not status.allowed:
            await self._incr_stat("rate_limited")
            return self._decide(user_id, False, "rate_limited", trace_id, status)

        if await self.injection.is_injection(text):
            await self._incr_stat("blocked_injections")
            return self._decide(user_id, False, "injection", trace_id, status)

        return self._decide(user_id, True, None, trace_id, status)

    def _decide(self, user_id, allowed, reason, trace_id, status) -> GatewayDecision:
        logger.info(
            "gateway decision: %s",
            {
                "user_id": user_id,
                "decision": "allow" if allowed else "block",
                "reason": reason,
                "trace_id": trace_id,
            },
        )
        return GatewayDecision(
            allowed=allowed,
            reason=reason,
            trace_id=trace_id,
            remaining=status.remaining,
            limit=status.limit,
            reset_seconds=status.reset_seconds,
        )

    async def _incr_stat(self, field: str) -> None:
        try:
            await self.redis.hincrby(_STATS_KEY, field, 1)
        except Exception as exc:
            logger.warning("gateway stats incr failed: %s", exc)

    async def stats(self) -> dict:
        try:
            raw = await self.redis.hgetall(_STATS_KEY)
        except Exception as exc:
            logger.warning("gateway stats read failed: %s", exc)
            raw = {}

        def _get(field: str) -> int:
            val = raw.get(field)
            if val is None:
                val = raw.get(field.encode())
            return int(val) if val is not None else 0

        return {
            "blocked_injections": _get("blocked_injections"),
            "rate_limited": _get("rate_limited"),
        }
