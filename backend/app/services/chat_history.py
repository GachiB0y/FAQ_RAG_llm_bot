from datetime import datetime, timezone, timedelta
from uuid import uuid4

from sqlalchemy import select, func, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Conversation, Message, MessageRole


async def get_or_create_conversation(user_id: str, db: AsyncSession) -> Conversation:
    """Get existing conversation for user or create a new one."""
    result = await db.execute(
        select(Conversation).where(Conversation.user_id == user_id)
    )
    conversation = result.scalar_one_or_none()

    if conversation is None:
        conversation = Conversation(id=str(uuid4()), user_id=user_id)
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)

    return conversation


async def get_history(
    user_id: str, limit: int, offset: int, db: AsyncSession
) -> tuple[list[Message], int]:
    """
    Get paginated chat history for user.
    Returns (messages_in_asc_order, total_count).
    Pagination: offset=0 returns the most recent `limit` messages.
    Messages are returned in chronological order (oldest first).
    """
    result = await db.execute(
        select(Conversation).where(Conversation.user_id == user_id)
    )
    conversation = result.scalar_one_or_none()

    if conversation is None:
        return [], 0

    # Count total messages
    count_result = await db.execute(
        select(func.count(Message.id)).where(
            Message.conversation_id == conversation.id
        )
    )
    total = count_result.scalar_one()

    if total == 0:
        return [], 0

    # Get messages newest-first (for offset), then reverse for chronological display
    messages_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    messages = list(messages_result.scalars().all())
    messages.reverse()  # chronological order for display

    return messages, total


async def delete_history(user_id: str, db: AsyncSession) -> int:
    """Delete all messages for user. Returns count of deleted messages."""
    result = await db.execute(
        select(Conversation).where(Conversation.user_id == user_id)
    )
    conversation = result.scalar_one_or_none()

    if conversation is None:
        return 0

    delete_result = await db.execute(
        delete(Message).where(Message.conversation_id == conversation.id)
    )
    await db.commit()

    return delete_result.rowcount


async def save_messages_pair(
    conversation_id: str,
    user_content: str,
    assistant_content: str,
    db: AsyncSession,
) -> None:
    """Save user + assistant message pair atomically in one transaction.

    Explicit created_at timestamps ensure user message always precedes
    assistant message even within the same DB transaction (where
    PostgreSQL's NOW() would return the same value for both).
    """
    now = datetime.now(timezone.utc)
    user_msg = Message(
        id=str(uuid4()),
        conversation_id=conversation_id,
        role=MessageRole.USER,
        content=user_content,
        created_at=now,
    )
    assistant_msg = Message(
        id=str(uuid4()),
        conversation_id=conversation_id,
        role=MessageRole.ASSISTANT,
        content=assistant_content,
        created_at=now + timedelta(microseconds=1),
    )
    db.add(user_msg)
    db.add(assistant_msg)

    await db.execute(
        update(Conversation)
        .where(Conversation.id == conversation_id)
        .values(updated_at=datetime.now(timezone.utc))
    )

    await db.commit()


async def cleanup_old_messages(retention_days: int, db: AsyncSession) -> int:
    """Delete messages older than retention_days. Returns count of deleted messages."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)

    result = await db.execute(
        delete(Message).where(Message.created_at < cutoff)
    )
    await db.commit()

    return result.rowcount
