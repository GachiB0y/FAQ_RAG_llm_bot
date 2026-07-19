# E1 — Telegram-бот поверх RAG. План реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Дать коллегам задавать вопросы по документам ФПСР через Telegram — бот-клиент вызывает существующий `/api/v1/chat`, возвращает ответ RAG + источники + остаток дневной квоты, с честным per-telegram-user учётом (rate-limit E4 + Langfuse).

**Architecture:** Отдельный сервис `bot/` (aiogram 3, long-polling) — тонкий HTTP-клиент бэкенда, без RAG-логики. Аутентифицируется как служебный bot-юзер (login на старте). Правки ядра: (1) `chat.py` берёт идентификатор для gateway+Langfuse из заголовка `X-Telegram-User-Id`, но **только** от bot-юзера; (2) gateway/лимитер отдают остаток квоты, `chat.py` кладёт его в заголовки `X-RateLimit-*` ответа.

**Tech Stack:** Python 3.11, aiogram 3.x, httpx, pydantic-settings, uv; бэкенд — FastAPI + Security Gateway (E4) + Langfuse (A3).

## Global Constraints

- Python `>=3.11` (и бэкенд, и бот).
- Бот — **отдельный** набор зависимостей (`bot/pyproject.toml`, uv), НЕ смешивать с бэкендом.
- Секреты (`TELEGRAM_BOT_TOKEN`, пароль bot-юзера) — только через env, в git не коммитить.
- Веб-контур `/api/v1/chat` НЕ менять по поведению: без заголовка `X-Telegram-User-Id` всё как раньше; заголовки `X-RateLimit-*` — чисто аддитивные, схема `ChatResponse` неизменна.
- Namespace идентификатора telegram-юзера — строка `tg:<telegram_id>` (Redis-ключ лимита + Langfuse `user_id`).
- Остаток квоты бот получает ТОЛЬКО из заголовков ответа (доступа к Redis у бота нет).
- Бэкенд-тесты — в контейнере: `docker exec faq_rag_llm_bot-backend-1 python -m pytest <path> -v` (код bind-mount `./backend:/app`, пересборка не нужна).
- Бот-тесты — на хосте: `cd bot && uv run pytest <path> -v`.
- Стиль кода — как в соседних файлах (русские комментарии где приняты; type hints; FastAPI `Annotated`).

---

## Файловая структура

**Правки бэкенда:**
- Create `backend/app/api/v1/actor.py` — чистая `resolve_actor_id`.
- Modify `backend/app/api/v1/chat.py` — заголовок tg-id + `resolve_actor_id` + заголовки `X-RateLimit-*`.
- Modify `backend/app/config.py` — `TELEGRAM_BOT_USER_EMAIL`.
- Modify `backend/app/core/gateway/rate_limiter.py` — `hit` + `RateLimitStatus`.
- Modify `backend/app/core/gateway/decision.py` — поля квоты.
- Modify `backend/app/core/gateway/gateway.py` — `check` заполняет поля.
- Create `backend/scripts/seed_bot.py` — сид bot-юзера (role=user).
- Test `backend/tests/test_actor.py`, `backend/tests/test_gateway_rate_limit.py` (дополнить), `backend/tests/test_chat_gateway_integration.py` (дополнить).

**Новый сервис бота (`bot/`):**
- `bot/pyproject.toml`, `bot/app/__init__.py`, `bot/app/config.py`.
- `bot/app/formatting.py` — `dedup_sources`, `format_duration`, `format_reply`.
- `bot/app/client.py` — `BackendClient`, `ChatResult` (с полями квоты).
- `bot/app/handlers.py` — роутер + `render_result`.
- `bot/app/main.py`, `bot/Dockerfile`, `bot/.dockerignore`.
- `bot/tests/test_formatting.py`, `test_client.py`, `test_handlers.py`.

**Инфраструктура:**
- Modify `docker-compose.yml`, `Makefile`, `.env.example`, `PROJECT_STATUS.md`.

---

## Task 1: Чистая функция `resolve_actor_id` (backend)

**Files:**
- Create: `backend/app/api/v1/actor.py`
- Test: `backend/tests/test_actor.py`

**Interfaces:**
- Produces: `resolve_actor_id(user_email: str, user_id: str, x_telegram_user_id: str | None, bot_email: str | None) -> str` — возвращает `f"tg:{x_telegram_user_id}"` только если заголовок непустой И `bot_email` задан И `user_email == bot_email`; иначе `user_id`.

- [ ] **Step 1: Написать падающие тесты**

`backend/tests/test_actor.py`:
```python
from app.api.v1.actor import resolve_actor_id

BOT = "bot@example.com"


def test_bot_user_with_header_uses_telegram_namespace():
    assert resolve_actor_id(BOT, "u-1", "12345", BOT) == "tg:12345"


def test_web_user_with_header_ignores_header():
    assert resolve_actor_id("web@example.com", "u-1", "12345", BOT) == "u-1"


def test_no_header_returns_user_id():
    assert resolve_actor_id(BOT, "u-1", None, BOT) == "u-1"


def test_empty_header_returns_user_id():
    assert resolve_actor_id(BOT, "u-1", "", BOT) == "u-1"


def test_bot_email_unset_returns_user_id():
    assert resolve_actor_id(BOT, "u-1", "12345", None) == "u-1"
```

- [ ] **Step 2: Запустить — убедиться, что падают**

Run: `docker exec faq_rag_llm_bot-backend-1 python -m pytest tests/test_actor.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.api.v1.actor'`.

- [ ] **Step 3: Реализовать функцию**

`backend/app/api/v1/actor.py`:
```python
"""Выбор идентификатора актора для rate-limit (E4) и Langfuse (A3).

Бот ходит под ОДНИМ служебным JWT, а конкретный telegram-юзер приходит в
заголовке X-Telegram-User-Id. Доверяем заголовку ТОЛЬКО когда запрос — от
служебного bot-юзера (сверка по email из настроек), иначе обычный веб-юзер
мог бы подделать чужой telegram id и сжечь его лимит.
"""


def resolve_actor_id(
    user_email: str,
    user_id: str,
    x_telegram_user_id: str | None,
    bot_email: str | None,
) -> str:
    if x_telegram_user_id and bot_email and user_email == bot_email:
        return f"tg:{x_telegram_user_id}"
    return user_id
```

- [ ] **Step 4: Запустить — убедиться, что проходят**

Run: `docker exec faq_rag_llm_bot-backend-1 python -m pytest tests/test_actor.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Коммит**

```bash
git add backend/app/api/v1/actor.py backend/tests/test_actor.py
git commit -m "feat(e1): resolve_actor_id — tg-namespace идентификатор для бота

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Прокинуть tg-id в `chat.py` + настройка (backend)

**Files:**
- Modify: `backend/app/config.py:49-54` (блок Security Gateway)
- Modify: `backend/app/api/v1/chat.py:40-88`
- Modify: `backend/tests/test_chat_gateway_integration.py`

**Interfaces:**
- Consumes: `resolve_actor_id(...)` (Task 1); `settings.TELEGRAM_BOT_USER_EMAIL`.
- Produces: эндпоинт учитывает `X-Telegram-User-Id` для gateway+Langfuse у bot-юзера.

- [ ] **Step 1: Добавить настройку в config.py**

В `backend/app/config.py`, в блок Security Gateway (после `OPENROUTER_API_KEY: Optional[str] = None`, ~строка 54):
```python
    # E1 — Telegram-бот: email служебного bot-юзера. Только его запросам доверяем
    # заголовок X-Telegram-User-Id (иначе веб-юзер подделал бы чужой tg id).
    TELEGRAM_BOT_USER_EMAIL: Optional[str] = None
```

- [ ] **Step 2: Обновить фикстуру и написать падающие интеграционные тесты**

В `backend/tests/test_chat_gateway_integration.py`:

(a) в фикстуре `client` дать `fake_user` поле `email` и добавить в fake-settings `TELEGRAM_BOT_USER_EMAIL`:
```python
    fake_user = SimpleNamespace(
        id="u-1",
        email="admin@example.com",
        is_active=True,
        role=SimpleNamespace(value="admin"),
    )
```
```python
    app.dependency_overrides[get_settings_dep] = lambda: SimpleNamespace(
        GATEWAY_ENABLED=True,
        TELEGRAM_BOT_USER_EMAIL="bot@example.com",
    )
```

(b) добавить в конец файла фикстуру bot-юзера и тест изоляции лимита:
```python
@pytest.fixture
def bot_client(monkeypatch):
    fake_redis = FakeRedis()
    bot_user = SimpleNamespace(
        id="bot-1",
        email="bot@example.com",
        is_active=True,
        role=SimpleNamespace(value="user"),
    )

    def _gateway():
        return SecurityGateway(
            RateLimiter(fake_redis, limit_per_day=10),
            InjectionGuard(classifier=None),
            fake_redis,
        )

    async def _fake_get_or_create_conversation(user_id, db):
        return SimpleNamespace(id="conv-1")

    async def _fake_save_messages_pair(conversation_id, q, a, db):
        return None

    monkeypatch.setattr(
        "app.api.v1.chat.get_or_create_conversation", _fake_get_or_create_conversation
    )
    monkeypatch.setattr(
        "app.api.v1.chat.save_messages_pair", _fake_save_messages_pair
    )

    async def _fake_db():
        yield None

    app.dependency_overrides[get_current_user] = lambda: bot_user
    app.dependency_overrides[get_rag_engine] = lambda: _FakeRag()
    app.dependency_overrides[get_redis] = lambda: fake_redis
    app.dependency_overrides[get_gateway] = _gateway
    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_settings_dep] = lambda: SimpleNamespace(
        GATEWAY_ENABLED=True,
        TELEGRAM_BOT_USER_EMAIL="bot@example.com",
    )

    yield TestClient(app)
    app.dependency_overrides.clear()


def test_per_telegram_user_rate_limit_is_isolated(bot_client):
    for _ in range(10):
        r = bot_client.post(
            "/api/v1/chat", json={"message": "ок"},
            headers={"X-Telegram-User-Id": "111"},
        )
        assert r.status_code == 200
    assert bot_client.post(
        "/api/v1/chat", json={"message": "ок"},
        headers={"X-Telegram-User-Id": "111"},
    ).status_code == 429

    assert bot_client.post(
        "/api/v1/chat", json={"message": "ок"},
        headers={"X-Telegram-User-Id": "222"},
    ).status_code == 200
```

- [ ] **Step 3: Запустить — убедиться, что новый тест падает**

Run: `docker exec faq_rag_llm_bot-backend-1 python -m pytest tests/test_chat_gateway_integration.py -v`
Expected: `test_per_telegram_user_rate_limit_is_isolated` FAIL — сейчас лимит по `str(user.id)="bot-1"` (общий), поэтому tg:222 упрётся в исчерпанный бакет и вернёт 429 вместо 200.

- [ ] **Step 4: Внести правку в chat.py**

В `backend/app/api/v1/chat.py`:

(a) импорт (после строки 21):
```python
from app.api.v1.actor import resolve_actor_id
```
(b) параметр-заголовок в сигнатуру `chat(...)` (после `x_gateway_bypass`, строка 50):
```python
    x_telegram_user_id: Annotated[str | None, Header()] = None,
```
(c) сразу после сигнатуры (перед `if gateway_applies(...)`, строка 52):
```python
    actor_id = resolve_actor_id(
        user.email, str(user.id), x_telegram_user_id, settings.TELEGRAM_BOT_USER_EMAIL
    )
```
(d) в вызове gateway `str(user.id)` → `actor_id` (строка 53):
```python
        decision = await gateway.check(actor_id, data.message)
```
(e) в `trace_context` `user_id=str(user.id)` → `user_id=actor_id` (строка 78):
```python
        user_id=actor_id,
```

> NB: `session_mgr.create_session(user.id)` и запись в Postgres (`get_or_create_conversation(user.id, ...)`) НЕ трогаем — сессия/история на реального bot-юзера, это ок.

- [ ] **Step 5: Запустить файл интеграционных тестов**

Run: `docker exec faq_rag_llm_bot-backend-1 python -m pytest tests/test_chat_gateway_integration.py -v`
Expected: PASS — новый тест зелёный, прежние (`test_clean_request_reaches_rag`, `test_rate_limit_returns_429`, `test_admin_bypass_header_skips_gateway`, `test_gateway_stats_counts_blocks`, `test_query_runs_and_returns_via_threadpool`) зелёные.

- [ ] **Step 6: Коммит**

```bash
git add backend/app/config.py backend/app/api/v1/chat.py backend/tests/test_chat_gateway_integration.py
git commit -m "feat(e1): chat.py учитывает X-Telegram-User-Id (per-tg-user лимит+Langfuse)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Остаток квоты в заголовках ответа (backend)

**Files:**
- Modify: `backend/app/core/gateway/rate_limiter.py`
- Modify: `backend/app/core/gateway/decision.py`
- Modify: `backend/app/core/gateway/gateway.py`
- Modify: `backend/app/api/v1/chat.py`
- Test: `backend/tests/test_gateway_rate_limit.py` (дополнить), `backend/tests/test_chat_gateway_integration.py` (дополнить)

**Interfaces:**
- Produces:
  - `RateLimitStatus(allowed: bool, remaining: int, limit: int, reset_seconds: int)` (dataclass в `rate_limiter.py`).
  - `RateLimiter.hit(user_id: str, today: date | None = None, now: datetime | None = None) -> RateLimitStatus`.
  - `GatewayDecision` + поля `remaining/limit/reset_seconds: int | None = None`.
  - Ответ `/api/v1/chat`: заголовки `X-RateLimit-Remaining`, `X-RateLimit-Limit`, `X-RateLimit-Reset` (на 200 и 429).

- [ ] **Step 1: Написать падающие unit-тесты `hit`**

Дополнить `backend/tests/test_gateway_rate_limit.py`:
```python
from datetime import datetime


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
```

- [ ] **Step 2: Запустить — убедиться, что падают**

Run: `docker exec faq_rag_llm_bot-backend-1 python -m pytest tests/test_gateway_rate_limit.py -v`
Expected: FAIL — у `RateLimiter` нет метода `hit` / нет `RateLimitStatus`.

- [ ] **Step 3: Реализовать `hit` + `RateLimitStatus`**

Переписать `backend/app/core/gateway/rate_limiter.py`:
```python
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
```

- [ ] **Step 4: Запустить — unit `hit` + старые тесты лимитера зелёные**

Run: `docker exec faq_rag_llm_bot-backend-1 python -m pytest tests/test_gateway_rate_limit.py -v`
Expected: PASS (старые `is_allowed`-тесты + 4 новых).

- [ ] **Step 5: Расширить `GatewayDecision` и `SecurityGateway.check`**

`backend/app/core/gateway/decision.py`:
```python
from dataclasses import dataclass


@dataclass
class GatewayDecision:
    allowed: bool
    reason: str | None  # "rate_limited" | "injection" | None
    trace_id: str
    remaining: int | None = None
    limit: int | None = None
    reset_seconds: int | None = None
```

В `backend/app/core/gateway/gateway.py` заменить тело `check` и `_decide`:
```python
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
```

- [ ] **Step 6: Проставить заголовки в `chat.py` + integration-тест**

(a) В `backend/app/api/v1/chat.py` импорт `Response`:
```python
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
```
(b) добавить параметр `response: Response` в сигнатуру `chat(...)` (например, сразу после `data: ChatRequest`):
```python
    response: Response,
```
(c) в ветке rate_limited — отдать заголовки в исключении:
```python
            if decision.reason == "rate_limited":
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Дневной лимит запросов исчерпан, попробуйте завтра",
                    headers={
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Limit": str(decision.limit),
                        "X-RateLimit-Reset": str(decision.reset_seconds),
                    },
                )
```
(d) после успешной проверки (сразу за блоком `if not decision.allowed: ...`, всё ещё внутри `if gateway_applies`) проставить заголовки успеха:
```python
        response.headers["X-RateLimit-Remaining"] = str(decision.remaining)
        response.headers["X-RateLimit-Limit"] = str(decision.limit)
        response.headers["X-RateLimit-Reset"] = str(decision.reset_seconds)
```

(e) дополнить `backend/tests/test_chat_gateway_integration.py` — заголовки на 200 и 429 (использует `bot_client` из Task 2):
```python
def test_ratelimit_headers_on_success(bot_client):
    r = bot_client.post(
        "/api/v1/chat", json={"message": "ок"},
        headers={"X-Telegram-User-Id": "555"},
    )
    assert r.status_code == 200
    assert r.headers["X-RateLimit-Limit"] == "10"
    assert r.headers["X-RateLimit-Remaining"] == "9"   # 1 использован
    assert int(r.headers["X-RateLimit-Reset"]) > 0


def test_ratelimit_headers_on_429(bot_client):
    for _ in range(10):
        bot_client.post(
            "/api/v1/chat", json={"message": "ок"},
            headers={"X-Telegram-User-Id": "556"},
        )
    r = bot_client.post(
        "/api/v1/chat", json={"message": "ок"},
        headers={"X-Telegram-User-Id": "556"},
    )
    assert r.status_code == 429
    assert r.headers["X-RateLimit-Remaining"] == "0"
    assert int(r.headers["X-RateLimit-Reset"]) > 0
```

- [ ] **Step 7: Прогнать gateway-тесты + весь бэкенд (регрессия)**

Run: `docker exec faq_rag_llm_bot-backend-1 python -m pytest tests/test_gateway_core.py tests/test_chat_gateway_integration.py -v && docker exec faq_rag_llm_bot-backend-1 python -m pytest -q`
Expected: PASS — новые тесты заголовков зелёные; `test_gateway_core` (проверяет `d.allowed/reason/trace_id`) не сломан новыми полями; общий прогон без падений.

- [ ] **Step 8: Коммит**

```bash
git add backend/app/core/gateway/rate_limiter.py backend/app/core/gateway/decision.py backend/app/core/gateway/gateway.py backend/app/api/v1/chat.py backend/tests/test_gateway_rate_limit.py backend/tests/test_chat_gateway_integration.py
git commit -m "feat(e1): остаток квоты в заголовках X-RateLimit-* (для бота)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Сид служебного bot-юзера (backend)

**Files:**
- Create: `backend/scripts/seed_bot.py`
- Modify: `Makefile` (таргет `bot-seed` + `.PHONY`)

**Interfaces:**
- Produces: `python scripts/seed_bot.py <email> <password>` создаёт (идемпотентно) пользователя role=user; `make bot-seed` вызывает его в контейнере.

- [ ] **Step 1: Написать скрипт**

`backend/scripts/seed_bot.py`:
```python
#!/usr/bin/env python3
"""Seed script: служебный bot-юзер для Telegram-бота (E1). Идемпотентно."""

import asyncio
import sys
from uuid import uuid4

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, "/app")

from app.config import get_settings
from app.models import User, UserRole

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def create_bot_user(email: str, password: str) -> None:
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        result = await session.execute(select(User).where(User.email == email))
        if result.scalar_one_or_none():
            print(f"Bot user {email} already exists")
            await engine.dispose()
            return

        bot = User(
            id=str(uuid4()),
            email=email,
            password_hash=pwd_context.hash(password),
            role=UserRole.USER,
            is_active=True,
        )
        session.add(bot)
        await session.commit()
        print(f"Bot user created: {email}")

    await engine.dispose()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: seed_bot.py <email> <password>", file=sys.stderr)
        sys.exit(1)
    asyncio.run(create_bot_user(sys.argv[1], sys.argv[2]))
```

- [ ] **Step 2: Добавить таргет в Makefile**

В `.PHONY`-список (строки 38-39) дописать `bot-seed bot-up bot-logs`. В конец Makefile добавить:
```makefile
# ─────────────── Telegram-бот (E1) ───────────────
bot-seed: ## Создать служебного bot-юзера (email/пароль из .env: TELEGRAM_BOT_EMAIL/PASSWORD)
	docker exec $(BACKEND) python scripts/seed_bot.py \
	  "$$(grep '^TELEGRAM_BOT_EMAIL=' .env | cut -d= -f2-)" \
	  "$$(grep '^TELEGRAM_BOT_PASSWORD=' .env | cut -d= -f2-)"
```
(таргеты `bot-up`/`bot-logs` добавим в Task 9; в `.PHONY` объявить можно сразу.)

- [ ] **Step 3: Проверить сид (при поднятом стеке)**

Run:
```bash
docker exec faq_rag_llm_bot-backend-1 python scripts/seed_bot.py bot@example.com testpass123
docker exec faq_rag_llm_bot-backend-1 python scripts/seed_bot.py bot@example.com testpass123
```
Expected: первый → `Bot user created: bot@example.com`; второй → `Bot user already exists`.

- [ ] **Step 4: Проверить login bot-юзера**

Run:
```bash
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"bot@example.com","password":"testpass123"}'
```
Expected: JSON с `access_token` и `refresh_token`.

- [ ] **Step 5: Коммит**

```bash
git add backend/scripts/seed_bot.py Makefile
git commit -m "feat(e1): seed_bot.py + make bot-seed — служебный bot-юзер (role=user)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Каркас бота + форматирование (ответ, источники, квота)

**Files:**
- Create: `bot/pyproject.toml`, `bot/app/__init__.py`, `bot/app/config.py`, `bot/app/formatting.py`
- Test: `bot/tests/test_formatting.py`

**Interfaces:**
- Produces:
  - `dedup_sources(sources: list[dict]) -> list[dict]` — дедуп по `(document, page)`, порядок сохраняется.
  - `format_duration(seconds: int) -> str` — «Xч Yм» (при 0 часов → «Yм»).
  - `format_reply(answer: str, sources: list[dict], remaining: int | None = None, limit: int | None = None) -> str` — ответ + блок «📎 Источники» + строка квоты (если `remaining` и `limit` заданы).
  - `bot.app.config.Settings` / `get_settings()`: `TELEGRAM_BOT_TOKEN`, `BACKEND_URL`, `TELEGRAM_BOT_EMAIL`, `TELEGRAM_BOT_PASSWORD`, `REQUEST_TIMEOUT`.

- [ ] **Step 1: Создать `bot/pyproject.toml`**

```toml
[project]
name = "faq-rag-telegram-bot"
version = "0.1.0"
description = "Telegram-бот поверх FAQ RAG (E1)"
requires-python = ">=3.11"
dependencies = [
    "aiogram>=3.13,<4",
    "httpx>=0.27",
    "pydantic-settings>=2.1",
]

[dependency-groups]
dev = [
    "pytest>=7.4",
    "pytest-asyncio>=0.23",
]

# Бот запускается из исходников — не пакет (uv не пытается его собирать).
[tool.uv]
package = false

[tool.pytest.ini_options]
asyncio_mode = "auto"
pythonpath = ["."]
```

- [ ] **Step 2: `bot/app/__init__.py` (пустой) и `bot/app/config.py`**

`bot/app/config.py`:
```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    TELEGRAM_BOT_TOKEN: str
    BACKEND_URL: str = "http://backend:8000"
    TELEGRAM_BOT_EMAIL: str
    TELEGRAM_BOT_PASSWORD: str
    REQUEST_TIMEOUT: float = 30.0

    model_config = SettingsConfigDict(env_file=".env")


def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 3: Написать падающие тесты форматирования**

`bot/tests/test_formatting.py`:
```python
from app.formatting import dedup_sources, format_duration, format_reply


def test_format_reply_answer_only():
    assert format_reply("Ответ.", []) == "Ответ."


def test_format_reply_with_sources():
    out = format_reply("Ответ.", [{"document": "Устав.pdf", "page": 3, "chunk": "..."}])
    assert out == "Ответ.\n\n📎 Источники:\n• Устав.pdf, стр. 3"


def test_format_reply_source_without_page():
    out = format_reply("Ответ.", [{"document": "FAQ.md", "page": None, "chunk": "x"}])
    assert out == "Ответ.\n\n📎 Источники:\n• FAQ.md"


def test_format_reply_appends_quota_line():
    out = format_reply("Ответ.", [], remaining=9, limit=10)
    assert out == "Ответ.\n\nОсталось 9 из 10 сообщений на сегодня."


def test_format_reply_sources_and_quota():
    out = format_reply(
        "Ответ.", [{"document": "A.pdf", "page": 1}], remaining=4, limit=10
    )
    assert out == (
        "Ответ.\n\n📎 Источники:\n• A.pdf, стр. 1"
        "\n\nОсталось 4 из 10 сообщений на сегодня."
    )


def test_dedup_sources_by_document_and_page():
    src = [
        {"document": "A.pdf", "page": 1},
        {"document": "A.pdf", "page": 1},
        {"document": "A.pdf", "page": 2},
    ]
    assert dedup_sources(src) == [
        {"document": "A.pdf", "page": 1},
        {"document": "A.pdf", "page": 2},
    ]


def test_format_duration_hours_and_minutes():
    assert format_duration(3 * 3600 + 12 * 60) == "3ч 12м"


def test_format_duration_minutes_only():
    assert format_duration(45 * 60) == "45м"
```

- [ ] **Step 4: Запустить — убедиться, что падают**

Run: `cd bot && uv run pytest tests/test_formatting.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.formatting'`.

- [ ] **Step 5: Реализовать `bot/app/formatting.py`**

```python
"""Форматирование ответа RAG для Telegram (простой текст, без разметки)."""


def dedup_sources(sources: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for s in sources:
        key = (s.get("document"), s.get("page"))
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


def format_duration(seconds: int) -> str:
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    if hours:
        return f"{hours}ч {minutes}м"
    return f"{minutes}м"


def format_reply(
    answer: str,
    sources: list[dict],
    remaining: int | None = None,
    limit: int | None = None,
) -> str:
    parts = [answer]

    unique = dedup_sources(sources)
    if unique:
        lines = ["📎 Источники:"]
        for s in unique:
            doc = s.get("document", "документ")
            page = s.get("page")
            lines.append(f"• {doc}, стр. {page}" if page is not None else f"• {doc}")
        parts.append("\n".join(lines))

    if remaining is not None and limit is not None:
        parts.append(f"Осталось {remaining} из {limit} сообщений на сегодня.")

    return "\n\n".join(parts)
```

- [ ] **Step 6: Запустить — убедиться, что проходят**

Run: `cd bot && uv run pytest tests/test_formatting.py -v`
Expected: PASS (8 passed).

- [ ] **Step 7: Коммит**

```bash
git add bot/pyproject.toml bot/app/__init__.py bot/app/config.py bot/app/formatting.py bot/tests/test_formatting.py
git commit -m "feat(e1): каркас бота (uv) + форматирование ответа/источников/квоты

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: HTTP-клиент бэкенда (`BackendClient`)

**Files:**
- Create: `bot/app/client.py`
- Test: `bot/tests/test_client.py`

**Interfaces:**
- Produces:
  - `ChatResult` (dataclass): `kind: str` ∈ {`"ok"`,`"rate_limited"`,`"rejected"`,`"error"`}; `answer: str = ""`; `sources: list[dict]`; `remaining: int | None = None`; `daily_limit: int | None = None`; `reset_seconds: int | None = None`.
  - `BackendClient(base_url, email, password, timeout=30.0, http=None)`; `async chat(text: str, telegram_user_id: int) -> ChatResult`; `async aclose()`.
  - Логин ленивый; на `401` — один перелогин и повтор; при повторном `401` → `ChatResult("error")`.
  - Заголовки `X-RateLimit-*` парсятся на 200 и 429.

- [ ] **Step 1: Написать падающие тесты (httpx.MockTransport)**

`bot/tests/test_client.py`:
```python
import httpx
import pytest

from app.client import BackendClient, ChatResult

OK_HEADERS = {
    "X-RateLimit-Remaining": "9",
    "X-RateLimit-Limit": "10",
    "X-RateLimit-Reset": "3600",
}


def _client(handler):
    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(transport=transport)
    return BackendClient("http://backend:8000", "bot@x", "pw", http=http)


@pytest.mark.asyncio
async def test_login_then_chat_ok_parses_headers():
    def handler(request):
        if request.url.path == "/api/v1/auth/login":
            return httpx.Response(200, json={"access_token": "T", "refresh_token": "R"})
        assert request.headers["Authorization"] == "Bearer T"
        assert request.headers["X-Telegram-User-Id"] == "42"
        return httpx.Response(200, headers=OK_HEADERS, json={
            "answer": "Ответ", "sources": [{"document": "A.pdf", "page": 1}],
            "confidence": 0.9, "session_id": "s",
        })

    res = await _client(handler).chat("вопрос", 42)
    assert res == ChatResult(
        kind="ok", answer="Ответ", sources=[{"document": "A.pdf", "page": 1}],
        remaining=9, daily_limit=10, reset_seconds=3600,
    )


@pytest.mark.asyncio
async def test_chat_429_parses_reset_headers():
    def handler(request):
        if request.url.path == "/api/v1/auth/login":
            return httpx.Response(200, json={"access_token": "T", "refresh_token": "R"})
        return httpx.Response(429, headers={
            "X-RateLimit-Remaining": "0", "X-RateLimit-Limit": "10",
            "X-RateLimit-Reset": "1800",
        }, json={"detail": "limit"})

    res = await _client(handler).chat("q", 1)
    assert res.kind == "rate_limited"
    assert res.reset_seconds == 1800
    assert res.daily_limit == 10


@pytest.mark.asyncio
async def test_chat_maps_400_to_rejected():
    def handler(request):
        if request.url.path == "/api/v1/auth/login":
            return httpx.Response(200, json={"access_token": "T", "refresh_token": "R"})
        return httpx.Response(400, json={"detail": "no"})

    assert (await _client(handler).chat("q", 1)).kind == "rejected"


@pytest.mark.asyncio
async def test_chat_maps_500_to_error():
    def handler(request):
        if request.url.path == "/api/v1/auth/login":
            return httpx.Response(200, json={"access_token": "T", "refresh_token": "R"})
        return httpx.Response(503, text="down")

    assert (await _client(handler).chat("q", 1)).kind == "error"


@pytest.mark.asyncio
async def test_chat_refreshes_token_on_401_then_succeeds():
    state = {"chat_calls": 0, "logins": 0}

    def handler(request):
        if request.url.path == "/api/v1/auth/login":
            state["logins"] += 1
            return httpx.Response(200, json={"access_token": "T", "refresh_token": "R"})
        state["chat_calls"] += 1
        if state["chat_calls"] == 1:
            return httpx.Response(401, json={"detail": "expired"})
        return httpx.Response(200, headers=OK_HEADERS, json={
            "answer": "ok", "sources": [], "confidence": 0.9, "session_id": "s",
        })

    res = await _client(handler).chat("q", 7)
    assert res.kind == "ok"
    assert state["logins"] == 2
    assert state["chat_calls"] == 2


@pytest.mark.asyncio
async def test_chat_network_error_maps_to_error():
    def handler(request):
        if request.url.path == "/api/v1/auth/login":
            return httpx.Response(200, json={"access_token": "T", "refresh_token": "R"})
        raise httpx.ConnectError("boom")

    assert (await _client(handler).chat("q", 1)).kind == "error"
```

- [ ] **Step 2: Запустить — убедиться, что падают**

Run: `cd bot && uv run pytest tests/test_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.client'`.

- [ ] **Step 3: Реализовать `bot/app/client.py`**

```python
"""Тонкий HTTP-клиент бэкенда FAQ RAG. Логин ленивый, на 401 — один перелогин.
Из заголовков X-RateLimit-* вытаскивает остаток квоты в ChatResult."""

import logging
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)

_AUTH_EXPIRED = "auth_expired"


@dataclass
class ChatResult:
    kind: str  # "ok" | "rate_limited" | "rejected" | "error"
    answer: str = ""
    sources: list[dict] = field(default_factory=list)
    remaining: int | None = None
    daily_limit: int | None = None
    reset_seconds: int | None = None


def _int_header(response: httpx.Response, name: str) -> int | None:
    raw = response.headers.get(name)
    return int(raw) if raw is not None else None


class BackendClient:
    def __init__(self, base_url, email, password, timeout=30.0, http=None):
        self._base = base_url.rstrip("/")
        self._email = email
        self._password = password
        self._http = http or httpx.AsyncClient(timeout=timeout)
        self._token: str | None = None

    async def _login(self) -> None:
        r = await self._http.post(
            f"{self._base}/api/v1/auth/login",
            json={"email": self._email, "password": self._password},
        )
        r.raise_for_status()
        self._token = r.json()["access_token"]

    async def chat(self, text: str, telegram_user_id: int) -> ChatResult:
        if self._token is None:
            await self._login()
        result = await self._post_chat(text, telegram_user_id)
        if result.kind == _AUTH_EXPIRED:
            await self._login()
            result = await self._post_chat(text, telegram_user_id)
            if result.kind == _AUTH_EXPIRED:
                return ChatResult(kind="error")
        return result

    async def _post_chat(self, text: str, telegram_user_id: int) -> ChatResult:
        try:
            r = await self._http.post(
                f"{self._base}/api/v1/chat",
                json={"message": text},
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "X-Telegram-User-Id": str(telegram_user_id),
                },
            )
        except httpx.HTTPError as exc:
            logger.warning("backend request failed: %s", exc)
            return ChatResult(kind="error")

        if r.status_code == 401:
            return ChatResult(kind=_AUTH_EXPIRED)
        if r.status_code == 429:
            return ChatResult(
                kind="rate_limited",
                remaining=0,
                daily_limit=_int_header(r, "X-RateLimit-Limit"),
                reset_seconds=_int_header(r, "X-RateLimit-Reset"),
            )
        if r.status_code == 400:
            return ChatResult(kind="rejected")
        if r.status_code >= 500:
            return ChatResult(kind="error")

        data = r.json()
        return ChatResult(
            kind="ok",
            answer=data["answer"],
            sources=data["sources"],
            remaining=_int_header(r, "X-RateLimit-Remaining"),
            daily_limit=_int_header(r, "X-RateLimit-Limit"),
            reset_seconds=_int_header(r, "X-RateLimit-Reset"),
        )

    async def aclose(self) -> None:
        await self._http.aclose()
```

- [ ] **Step 4: Запустить — убедиться, что проходят**

Run: `cd bot && uv run pytest tests/test_client.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Коммит**

```bash
git add bot/app/client.py bot/tests/test_client.py
git commit -m "feat(e1): BackendClient — login/chat + перелогин на 401 + парсинг квоты

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: Хендлеры aiogram + маппинг результата в текст

**Files:**
- Create: `bot/app/handlers.py`
- Test: `bot/tests/test_handlers.py`

**Interfaces:**
- Consumes: `ChatResult` (Task 6), `format_reply`/`format_duration` (Task 5).
- Produces:
  - `render_result(result: ChatResult) -> str` — чистая функция: `ok`→`format_reply(answer, sources, remaining, daily_limit)`; `rate_limited`→текст лимита с `format_duration(reset_seconds)`; `rejected`/`error`→фикс-тексты.
  - `router: aiogram.Router` с `/start` и обработчиком текста (внедрённый `client`).
  - Константы: `WELCOME`, `MSG_REJECTED`, `MSG_ERROR`.

- [ ] **Step 1: Написать падающие тесты `render_result`**

`bot/tests/test_handlers.py`:
```python
from app.client import ChatResult
from app.handlers import render_result, MSG_REJECTED, MSG_ERROR


def test_render_ok_includes_answer_sources_and_quota():
    out = render_result(ChatResult(
        kind="ok", answer="Ответ",
        sources=[{"document": "A.pdf", "page": 2}],
        remaining=8, daily_limit=10,
    ))
    assert "Ответ" in out
    assert "📎 Источники:" in out
    assert "A.pdf, стр. 2" in out
    assert "Осталось 8 из 10" in out


def test_render_rate_limited_shows_reset_time():
    out = render_result(ChatResult(
        kind="rate_limited", daily_limit=10, reset_seconds=2 * 3600 + 30 * 60,
    ))
    assert "лимит" in out.lower()
    assert "2ч 30м" in out


def test_render_rejected():
    assert render_result(ChatResult(kind="rejected")) == MSG_REJECTED


def test_render_error():
    assert render_result(ChatResult(kind="error")) == MSG_ERROR
```

- [ ] **Step 2: Запустить — убедиться, что падают**

Run: `cd bot && uv run pytest tests/test_handlers.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.handlers'`.

- [ ] **Step 3: Реализовать `bot/app/handlers.py`**

```python
"""aiogram-роутер бота: /start и обработка вопросов. RAG-логики нет —
всё уходит в BackendClient, ответ маппится в текст render_result."""

from aiogram import Router
from aiogram.enums import ChatAction
from aiogram.filters import CommandStart
from aiogram.types import Message

from app.client import BackendClient, ChatResult
from app.formatting import format_duration, format_reply

router = Router()

WELCOME = (
    "Здравствуйте! Я отвечаю на вопросы по документам ФПСР. "
    "Просто напишите вопрос."
)
MSG_REJECTED = "Извините, я не могу обработать этот запрос."
MSG_ERROR = "Сервис временно недоступен, попробуйте позже."


def render_result(result: ChatResult) -> str:
    if result.kind == "ok":
        return format_reply(
            result.answer, result.sources, result.remaining, result.daily_limit
        )
    if result.kind == "rate_limited":
        limit = result.daily_limit if result.daily_limit is not None else "?"
        reset = (
            format_duration(result.reset_seconds)
            if result.reset_seconds is not None
            else "завтра"
        )
        return f"Вы исчерпали дневной лимит ({limit}/день). Лимит обновится через {reset}."
    if result.kind == "rejected":
        return MSG_REJECTED
    return MSG_ERROR


@router.message(CommandStart())
async def on_start(message: Message) -> None:
    await message.answer(WELCOME)


@router.message()
async def on_question(message: Message, client: BackendClient) -> None:
    if not message.text:
        return
    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    result = await client.chat(message.text, message.from_user.id)
    await message.answer(render_result(result))
```

- [ ] **Step 4: Запустить — убедиться, что проходят**

Run: `cd bot && uv run pytest tests/test_handlers.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Коммит**

```bash
git add bot/app/handlers.py bot/tests/test_handlers.py
git commit -m "feat(e1): хендлеры бота (/start, вопрос) + render_result с квотой/сбросом

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 8: Bootstrap polling + Dockerfile бота

**Files:**
- Create: `bot/app/main.py`, `bot/Dockerfile`, `bot/.dockerignore`

**Interfaces:**
- Consumes: `get_settings` (Task 5), `BackendClient` (Task 6), `router` (Task 7).
- Produces: запускаемый процесс `python -m app.main` (long-polling); образ бота.

> Без юнит-тестов (bootstrap-склейка протестированных частей). Проверка — импорт-смоук + сборка образа.

- [ ] **Step 1: Реализовать `bot/app/main.py`**

```python
"""Точка входа бота: long-polling. Клиент кладём в workflow_data диспетчера —
aiogram внедрит его в хендлер по имени параметра `client`."""

import asyncio
import logging

from aiogram import Bot, Dispatcher

from app.client import BackendClient
from app.config import get_settings
from app.handlers import router


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()

    client = BackendClient(
        base_url=settings.BACKEND_URL,
        email=settings.TELEGRAM_BOT_EMAIL,
        password=settings.TELEGRAM_BOT_PASSWORD,
        timeout=settings.REQUEST_TIMEOUT,
    )
    bot = Bot(settings.TELEGRAM_BOT_TOKEN)
    dp = Dispatcher()
    dp["client"] = client
    dp.include_router(router)

    try:
        await dp.start_polling(bot)
    finally:
        await client.aclose()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Смоук — импорт main без запуска polling**

Run: `cd bot && TELEGRAM_BOT_TOKEN=x TELEGRAM_BOT_EMAIL=b@x TELEGRAM_BOT_PASSWORD=p uv run python -c "import app.main; print('import ok')"`
Expected: `import ok`.

- [ ] **Step 3: Прогнать все тесты бота**

Run: `cd bot && uv run pytest -v`
Expected: PASS (formatting 8 + client 6 + handlers 4 = 18 passed).

- [ ] **Step 4: Создать `bot/Dockerfile`**

```dockerfile
FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV UV_PROJECT_ENVIRONMENT=/opt/venv

# Только прод-зависимости (без dev/pytest). Lock создастся при первой сборке.
COPY pyproject.toml ./
RUN uv sync --no-dev

ENV PATH="/opt/venv/bin:$PATH"

COPY . .

CMD ["python", "-m", "app.main"]
```

`bot/.dockerignore`:
```
tests/
__pycache__/
*.pyc
.env
```

- [ ] **Step 5: Собрать образ бота**

Run: `docker build -t faq-bot-test ./bot`
Expected: сборка успешна.

- [ ] **Step 6: Коммит**

```bash
git add bot/app/main.py bot/Dockerfile bot/.dockerignore
git commit -m "feat(e1): bootstrap polling + Dockerfile бота

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 9: Интеграция в docker-compose + Makefile + .env

**Files:**
- Modify: `docker-compose.yml` (сервис `telegram-bot` + env backend)
- Modify: `Makefile` (таргеты `bot-up`, `bot-logs`)
- Modify: `.env.example`

**Interfaces:**
- Produces: `make bot-up` поднимает бота; backend знает `TELEGRAM_BOT_USER_EMAIL`.

- [ ] **Step 1: env в backend-сервис `docker-compose.yml`**

В блок `backend.environment` (после `LANGFUSE_TRACING_ENVIRONMENT=production`, ~строка 24):
```yaml
      - TELEGRAM_BOT_USER_EMAIL=${TELEGRAM_BOT_EMAIL:-bot@example.com}
```

- [ ] **Step 2: сервис `telegram-bot`**

После блока `frontend` (перед `postgres`):
```yaml
  telegram-bot:
    build: ./bot
    environment:
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN:-}
      - BACKEND_URL=http://backend:8000
      - TELEGRAM_BOT_EMAIL=${TELEGRAM_BOT_EMAIL:-bot@example.com}
      - TELEGRAM_BOT_PASSWORD=${TELEGRAM_BOT_PASSWORD:-}
    depends_on:
      - backend
    restart: unless-stopped
```

- [ ] **Step 3: таргеты в Makefile**

В конец блока «Telegram-бот» (из Task 4):
```makefile
bot-up: ## Поднять сервис telegram-bot (после make up + make bot-seed)
	docker compose up -d --build telegram-bot

bot-logs: ## Логи бота (follow)
	docker compose logs -f telegram-bot
```

- [ ] **Step 4: `.env.example`**

В конец `.env.example`:
```
# Telegram-бот (E1)
TELEGRAM_BOT_TOKEN=
TELEGRAM_BOT_EMAIL=bot@example.com
TELEGRAM_BOT_PASSWORD=change-me
```

- [ ] **Step 5: Проверить валидность compose**

Run: `docker compose config --quiet && echo "compose ok"`
Expected: `compose ok`.

- [ ] **Step 6: Коммит**

```bash
git add docker-compose.yml Makefile .env.example
git commit -m "feat(e1): telegram-bot в docker-compose + make bot-up/bot-logs + .env.example

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 10: Ручной смоук-прогон + обновление статуса

**Files:**
- Modify: `PROJECT_STATUS.md`

> Требует реального `TELEGRAM_BOT_TOKEN` (@BotFather) и запущенного стека. Нет токена → выполнить проверки 1-2 (не требуют Telegram), живой прогон (3) отметить отложенным, галочку E1 не ставить «полностью».

- [ ] **Step 1: Подготовить окружение**

- В `.env`: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_EMAIL`, `TELEGRAM_BOT_PASSWORD`, `OPENROUTER_API_KEY` (для live-генератора M1).
- Поднять:
```bash
make up
make bot-seed
make bot-up
```
Expected: контейнеры `backend`, `telegram-bot` в статусе Up.

- [ ] **Step 2: Проверить per-tg учёт + заголовки квоты через API**

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"bot@example.com","password":"'"$(grep '^TELEGRAM_BOT_PASSWORD=' .env | cut -d= -f2-)"'"}' | python -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
curl -s -D - -o /dev/null -X POST http://localhost:8000/api/v1/chat \
  -H "Authorization: Bearer $TOKEN" -H "X-Telegram-User-Id: 777" \
  -H 'Content-Type: application/json' -d '{"message":"Как вступить в организацию?"}'
```
Expected: в заголовках ответа `X-RateLimit-Remaining: 9`, `X-RateLimit-Limit: 10`, `X-RateLimit-Reset: <секунды>`. (При включённом Langfuse — трейс с `user_id=tg:777`.)

- [ ] **Step 3: Живой прогон в Telegram**

- `/start` → приветствие.
- Вопрос по документам ФПСР → ответ + «📎 Источники» + строка «Осталось N из 10…».
- >10 вопросов подряд → «лимит обновится через Xч Yм».

Expected: все три сценария ок; `make bot-logs` без трейсбеков.

- [ ] **Step 4: Обновить PROJECT_STATUS.md**

- `- [x] **E1** ...` в «Линия E».
- В «ТЕКУЩИЙ ФОКУС» сдвинуть «Следующее действие» (E1 → E2/E5).
- Строка в «Хронологию» (2026-07-19): E1 + бот + показ квоты, ссылки на spec/план.

- [ ] **Step 5: Коммит**

```bash
git add PROJECT_STATUS.md
git commit -m "docs(e1): Telegram-бот готов — статус + хронология

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Порядок и зависимости задач

- Task 1 → Task 2 → Task 3 (chat.py правится в 2 и 3; лимитер/gateway — в 3).
- Task 4 (сид) независим от бота, нужен для смоука (Task 10).
- Task 5 → Task 6 → Task 7 → Task 8 (каркас → клиент → хендлеры → bootstrap).
- Task 9 зависит от Task 8 (Dockerfile) и Task 4 (bot-seed в Makefile-блоке).
- Task 10 — последний, требует всего + реального токена.

Backend-ветка (1→2→3, + 4) и бот-ветка (5→6→7→8) не пересекаются по файлам — можно вести параллельно; сходятся в Task 9.
