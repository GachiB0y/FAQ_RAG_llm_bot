"""Общие тест-фикстуры. FakeRedis — минимальный async in-memory стенд под
redis.asyncio (только методы, которые реально использует Gateway и SessionManager)."""


class FakeRedis:
    def __init__(self):
        self.kv = {}          # str -> str
        self.expires = {}     # str -> ttl (последний EXPIRE/SETEX)
        self.hashes = {}      # str -> {field(str): int}

    async def incr(self, key):
        self.kv[key] = int(self.kv.get(key, 0)) + 1
        return self.kv[key]

    async def expire(self, key, ttl):
        self.expires[key] = ttl
        return True

    async def get(self, key):
        return self.kv.get(key)

    async def setex(self, key, ttl, value):
        self.kv[key] = value
        self.expires[key] = ttl

    async def hincrby(self, key, field, amount=1):
        h = self.hashes.setdefault(key, {})
        h[field] = int(h.get(field, 0)) + amount
        return h[field]

    async def hgetall(self, key):
        h = self.hashes.get(key, {})
        return {k.encode(): str(v).encode() for k, v in h.items()}

    async def close(self):
        pass
