from typing import Annotated
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import redis.asyncio as redis

from app.database import get_db
from app.config import get_settings, Settings
from app.services.auth_service import AuthService
from app.models.user import User
from app.core.rag import RAGEngine
from app.core.llm import create_llm_adapter
from app.core.gateway.gateway import SecurityGateway
from app.core.gateway.rate_limiter import RateLimiter
from app.core.gateway.injection import InjectionGuard
from app.core.gateway.classifier import build_openrouter_classifier

security = HTTPBearer()


def get_settings_dep() -> Settings:
    return get_settings()


async def get_redis(settings: Annotated[Settings, Depends(get_settings_dep)]):
    client = redis.from_url(settings.REDIS_URL)
    try:
        yield client
    finally:
        await client.close()


def get_auth_service(settings: Annotated[Settings, Depends(get_settings_dep)]) -> AuthService:
    return AuthService(
        jwt_secret=settings.JWT_SECRET,
        jwt_expire_minutes=settings.JWT_EXPIRE_MINUTES
    )


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    auth: Annotated[AuthService, Depends(get_auth_service)],
    db: Annotated[AsyncSession, Depends(get_db)]
) -> User:
    payload = auth.decode_token(credentials.credentials)
    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )

    return user


async def get_admin_user(
    user: Annotated[User, Depends(get_current_user)]
) -> User:
    if user.role.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return user


def get_rag_engine(settings: Annotated[Settings, Depends(get_settings_dep)]) -> RAGEngine:
    llm_adapter = create_llm_adapter(settings)
    return RAGEngine(
        llm_adapter=llm_adapter,
        qdrant_url=settings.QDRANT_URL,
        similarity_threshold=settings.SIMILARITY_THRESHOLD,
        top_k=settings.TOP_K_RESULTS
    )


def get_session_id(x_session_id: str | None = Header(None)) -> str | None:
    return x_session_id


def get_gateway(
    settings: Annotated[Settings, Depends(get_settings_dep)],
    redis_client: Annotated[redis.Redis, Depends(get_redis)],
) -> SecurityGateway:
    rate_limiter = RateLimiter(redis_client, settings.RATE_LIMIT_PER_DAY)
    classifier = build_openrouter_classifier(settings)
    guard = InjectionGuard(classifier=classifier)
    return SecurityGateway(rate_limiter, guard, redis_client)
