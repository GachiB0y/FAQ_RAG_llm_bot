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
