from datetime import datetime, timezone, timedelta
from uuid import uuid4

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Conversation, Message


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


async def save_message(
    conversation_id: str, role: str, content: str, db: AsyncSession
) -> Message:
    """Save a single message to the conversation."""
    message = Message(
        id=str(uuid4()),
        conversation_id=conversation_id,
        role=role,
        content=content,
    )
    db.add(message)

    # Update conversation updated_at
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()
    if conversation:
        conversation.updated_at = datetime.now(timezone.utc)

    await db.commit()
    return message


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

    count_result = await db.execute(
        select(func.count(Message.id)).where(
            Message.conversation_id == conversation.id
        )
    )
    count = count_result.scalar_one()

    await db.execute(
        delete(Message).where(Message.conversation_id == conversation.id)
    )
    await db.commit()

    return count


async def cleanup_old_messages(retention_days: int, db: AsyncSession) -> int:
    """Delete messages older than retention_days. Returns count of deleted messages."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)

    count_result = await db.execute(
        select(func.count(Message.id)).where(Message.created_at < cutoff)
    )
    count = count_result.scalar_one()

    await db.execute(
        delete(Message).where(Message.created_at < cutoff)
    )
    await db.commit()

    return count
