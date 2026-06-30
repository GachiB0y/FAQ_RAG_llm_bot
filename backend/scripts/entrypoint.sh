#!/bin/bash
set -e

echo "Waiting for database..."
while ! nc -z postgres 5432; do
  sleep 1
done
echo "Database is ready!"

echo "Waiting for Ollama..."
while ! nc -z ollama 11434; do
  sleep 1
done
echo "Ollama is ready!"

echo "Pulling Ollama models (this may take a while on first run)..."
curl -s http://ollama:11434/api/pull -d '{"name": "qwen3:1.7b"}' | tail -1
curl -s http://ollama:11434/api/pull -d '{"name": "bge-m3"}' | tail -1

echo "Running migrations..."
alembic upgrade head

echo "Seeding admin user..."
python -c "
import asyncio, sys
sys.path.insert(0, '/app')
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from passlib.context import CryptContext
from app.config import get_settings

async def seed():
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL)
    ctx = CryptContext(schemes=['bcrypt'], deprecated='auto')
    async with engine.begin() as conn:
        result = await conn.execute(text(\"SELECT id FROM users WHERE email = 'admin@example.com'\"))
        if result.fetchone():
            print('Admin user already exists')
        else:
            pw = ctx.hash('admin123')
            await conn.execute(text(
                \"INSERT INTO users (id, email, password_hash, role, is_active, created_at, updated_at) \"
                \"VALUES (gen_random_uuid(), 'admin@example.com', :pw, 'admin', true, NOW(), NOW())\"
            ), {'pw': pw})
            print('Admin user created: admin@example.com / admin123')
    await engine.dispose()

asyncio.run(seed())
" || echo "Seed skipped (non-critical)"

echo "Starting server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
