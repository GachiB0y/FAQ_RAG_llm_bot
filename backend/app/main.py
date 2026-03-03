import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.config import get_settings
from app.database import AsyncSessionLocal
from app.services.chat_history import cleanup_old_messages

logger = logging.getLogger(__name__)

CLEANUP_INTERVAL_SECONDS = 86400  # 24 hours


async def _cleanup_loop(retention_days: int) -> None:
    """Background task: delete messages older than retention_days every 24h."""
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
        try:
            async with AsyncSessionLocal() as db:
                deleted = await cleanup_old_messages(retention_days, db)
                if deleted > 0:
                    logger.info(
                        f"Cleanup: deleted {deleted} messages older than {retention_days} days"
                    )
        except Exception as exc:
            logger.error(f"Cleanup task error: {exc}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    print(f"Starting FAQ RAG Bot with LLM provider: {settings.LLM_PROVIDER}")

    cleanup_task = asyncio.create_task(
        _cleanup_loop(settings.CHAT_HISTORY_RETENTION_DAYS)
    )

    yield

    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass

    print("Shutting down FAQ RAG Bot")


app = FastAPI(
    title="FAQ RAG Bot API",
    description="RAG-based FAQ Bot for documentation Q&A",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
