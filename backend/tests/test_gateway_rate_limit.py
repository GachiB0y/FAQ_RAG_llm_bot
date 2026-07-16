from datetime import date

from app.core.gateway.rate_limiter import RateLimiter
from tests.conftest import FakeRedis


async def test_allows_up_to_limit_then_blocks():
    limiter = RateLimiter(FakeRedis(), limit_per_day=10)
    results = [await limiter.is_allowed("u1") for _ in range(11)]
    assert results[:10] == [True] * 10   # первые 10 проходят
    assert results[10] is False          # 11-й — за лимитом


async def test_sets_ttl_on_first_hit():
    fake = FakeRedis()
    limiter = RateLimiter(fake, limit_per_day=10)
    await limiter.is_allowed("u1")
    key = f"ratelimit:u1:{date.today().isoformat()}"
    assert fake.expires[key] == 86400


async def test_counter_is_per_day_key():
    # разные дни → независимые счётчики (эмуляция сброса после TTL)
    fake = FakeRedis()
    limiter = RateLimiter(fake, limit_per_day=1)
    d1, d2 = date(2026, 7, 16), date(2026, 7, 17)
    assert await limiter.is_allowed("u1", today=d1) is True
    assert await limiter.is_allowed("u1", today=d1) is False  # лимит=1 исчерпан
    assert await limiter.is_allowed("u1", today=d2) is True   # новый день — сброс


async def test_fail_open_on_redis_error():
    class BrokenRedis:
        async def incr(self, key):
            raise RuntimeError("redis down")
    limiter = RateLimiter(BrokenRedis(), limit_per_day=10)
    assert await limiter.is_allowed("u1") is True  # fail-open
