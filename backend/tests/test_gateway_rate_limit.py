from datetime import date, datetime

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


async def test_hit_reports_decreasing_remaining():
    limiter = RateLimiter(FakeRedis(), limit_per_day=3)
    s1 = await limiter.hit("u1")
    s2 = await limiter.hit("u1")
    assert (s1.allowed, s1.remaining, s1.limit) == (True, 2, 3)
    assert (s2.allowed, s2.remaining) == (True, 1)


async def test_hit_remaining_not_negative_over_limit():
    limiter = RateLimiter(FakeRedis(), limit_per_day=1)
    await limiter.hit("u1")
    s = await limiter.hit("u1")            # 2-й вызов при лимите 1
    assert s.allowed is False
    assert s.remaining == 0                # не уходит в минус


async def test_hit_reset_seconds_positive():
    # 23:00 → до полуночи ~3600 c
    limiter = RateLimiter(FakeRedis(), limit_per_day=10)
    s = await limiter.hit("u1", now=datetime(2026, 7, 19, 23, 0, 0))
    assert 3500 <= s.reset_seconds <= 3600


async def test_hit_fail_open_reports_full_quota():
    class BrokenRedis:
        async def incr(self, key):
            raise RuntimeError("down")
    s = await RateLimiter(BrokenRedis(), limit_per_day=10).hit("u1")
    assert s.allowed is True and s.remaining == 10
