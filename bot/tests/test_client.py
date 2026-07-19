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
    assert res.remaining == 0
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


@pytest.mark.asyncio
async def test_chat_login_503_maps_to_error():
    """Finding 1: login raises HTTPStatusError (5xx) → chat() returns ChatResult(kind='error')."""
    def handler(request):
        if request.url.path == "/api/v1/auth/login":
            return httpx.Response(503, text="unavailable")
        return httpx.Response(200, headers=OK_HEADERS, json={
            "answer": "ok", "sources": [], "confidence": 0.9, "session_id": "s",
        })

    res = await _client(handler).chat("q", 1)
    assert res.kind == "error"


@pytest.mark.asyncio
async def test_chat_403_maps_to_error():
    """Finding 2: unexpected 4xx (403) → ChatResult(kind='error')."""
    def handler(request):
        if request.url.path == "/api/v1/auth/login":
            return httpx.Response(200, json={"access_token": "T", "refresh_token": "R"})
        return httpx.Response(403, json={"detail": "forbidden"})

    assert (await _client(handler).chat("q", 1)).kind == "error"


@pytest.mark.asyncio
async def test_chat_double_401_maps_to_error():
    """Finding 3: login ok → first chat 401 → re-login ok → second chat 401 → error."""
    state = {"logins": 0}

    def handler(request):
        if request.url.path == "/api/v1/auth/login":
            state["logins"] += 1
            return httpx.Response(200, json={"access_token": "T", "refresh_token": "R"})
        return httpx.Response(401, json={"detail": "expired"})

    res = await _client(handler).chat("q", 1)
    assert res.kind == "error"
    assert state["logins"] == 2
