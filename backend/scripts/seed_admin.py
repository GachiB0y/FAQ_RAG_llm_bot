#!/usr/bin/env python3
"""Seed script to create initial admin user."""

import asyncio
import sys
from uuid import uuid4

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Add parent directory to path
sys.path.insert(0, '/app')

from app.config import get_settings
from app.models import User, UserRole

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def create_admin(
    email: str = "admin@example.com",
    password: str = "admin123",
) -> None:
    """Create admin user if not exists."""
    settings = get_settings()
    
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Check if admin already exists
        result = await session.execute(
            select(User).where(User.email == email)
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            print(f"User {email} already exists")
            return
        
        # Create admin user
        admin = User(
            id=str(uuid4()),
            email=email,
            password_hash=pwd_context.hash(password),
            role=UserRole.ADMIN,
            is_active=True,
        )
        session.add(admin)
        await session.commit()
        
        print(f"Admin user created: {email}")
        print(f"Password: {password}")
        print("Please change the password after first login!")
    
    await engine.dispose()


if __name__ == "__main__":
    email = sys.argv[1] if len(sys.argv) > 1 else "admin@example.com"
    password = sys.argv[2] if len(sys.argv) > 2 else "admin123"
    
    asyncio.run(create_admin(email, password))
