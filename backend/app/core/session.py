import json
from uuid import uuid4
import redis.asyncio as redis


class SessionManager:
    SESSION_TTL = 86400  # 24 hours

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    def _key(self, session_id: str) -> str:
        return f"session:{session_id}"

    async def create_session(self, user_id: str) -> str:
        session_id = str(uuid4())
        data = {
            "user_id": user_id,
            "messages": []
        }
        await self.redis.setex(
            self._key(session_id),
            self.SESSION_TTL,
            json.dumps(data)
        )
        return session_id

    async def get_session(self, session_id: str) -> dict | None:
        data = await self.redis.get(self._key(session_id))
        if data:
            return json.loads(data)
        return None

    async def add_message(self, session_id: str, role: str, content: str):
        session = await self.get_session(session_id)
        if session:
            session["messages"].append({"role": role, "content": content})
            session["messages"] = session["messages"][-10:]
            await self.redis.setex(
                self._key(session_id),
                self.SESSION_TTL,
                json.dumps(session)
            )

    async def get_history(self, session_id: str) -> list[dict]:
        session = await self.get_session(session_id)
        if session:
            return session.get("messages", [])
        return []
