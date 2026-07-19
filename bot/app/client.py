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
            try:
                await self._login()
            except httpx.HTTPError as exc:
                logger.warning("login failed: %s", exc)
                return ChatResult(kind="error")
        result = await self._post_chat(text, telegram_user_id)
        if result.kind == _AUTH_EXPIRED:
            try:
                await self._login()
            except httpx.HTTPError as exc:
                logger.warning("re-login failed: %s", exc)
                return ChatResult(kind="error")
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
        if r.status_code >= 400:
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
