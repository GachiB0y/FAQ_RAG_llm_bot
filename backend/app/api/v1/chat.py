from typing import Annotated
from fastapi import APIRouter, Depends, Query
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_user,
    get_rag_engine,
    get_redis,
    get_session_id,
)
from app.database import get_db
from app.models.user import User
from app.core.rag import RAGEngine
from app.core.session import SessionManager
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ChatHistoryResponse,
    ChatHistoryItem,
    DeleteHistoryResponse,
)
from app.services.chat_history import (
    get_or_create_conversation,
    save_messages_pair,
    get_history,
    delete_history,
)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(
    data: ChatRequest,
    user: Annotated[User, Depends(get_current_user)],
    rag: Annotated[RAGEngine, Depends(get_rag_engine)],
    redis_client: Annotated[redis.Redis, Depends(get_redis)],
    session_id: Annotated[str | None, Depends(get_session_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    session_mgr = SessionManager(redis_client)

    # Redis: manage hot context for RAG (unchanged)
    if session_id:
        session = await session_mgr.get_session(session_id)
        if not session:
            session_id = await session_mgr.create_session(user.id)
    else:
        session_id = await session_mgr.create_session(user.id)

    history = await session_mgr.get_history(session_id)

    result = rag.query(data.message, chat_history=history)

    # PostgreSQL: persist messages permanently (atomic pair, durable first)
    conversation = await get_or_create_conversation(user.id, db)
    await save_messages_pair(conversation.id, data.message, result["answer"], db)

    # Redis: update hot context for RAG
    await session_mgr.add_message(session_id, "user", data.message)
    await session_mgr.add_message(session_id, "assistant", result["answer"])

    return ChatResponse(
        answer=result["answer"],
        sources=result["sources"],
        confidence=result["confidence"],
        session_id=session_id,
    )


@router.get("/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    messages, total = await get_history(user.id, limit, offset, db)

    return ChatHistoryResponse(
        messages=[
            ChatHistoryItem(
                role=msg.role,
                content=msg.content,
                created_at=msg.created_at,
            )
            for msg in messages
        ],
        total=total,
        limit=limit,
        offset=offset,
        has_more=(offset + limit) < total,
    )


@router.delete("/history", response_model=DeleteHistoryResponse)
async def clear_chat_history(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    deleted_count = await delete_history(user.id, db)
    return DeleteHistoryResponse(deleted_count=deleted_count)
