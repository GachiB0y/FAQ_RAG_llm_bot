#!/usr/bin/env python3
"""
Грузит PDF-файлы из локальной папки в Qdrant + создаёт записи в Postgres.

Использует существующий RAGEngine.add_document — никакого нового кода для парсинга.

Запуск (внутри backend контейнера):
    docker exec faq_rag_llm_bot-backend-1 python scripts/ingest_local.py /tmp/corpus
"""

import asyncio
import os
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, "/app")

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.llm.ollama import OllamaAdapter
from app.core.rag.engine import RAGEngine
from app.models.document import Document, DocumentStatus
from app.models.user import User

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434")
QDRANT_URL = os.environ.get("QDRANT_URL", "http://qdrant:6333")
DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+asyncpg://faq_user:faq_pass@postgres:5432/faq_bot"
)
GENERATOR_MODEL = "qwen3:1.7b"
EMBEDDING_MODEL = "bge-m3"


async def get_admin_id(session: AsyncSession) -> str:
    result = await session.execute(
        select(User.id).where(User.email == "admin@example.com")
    )
    row = result.first()
    if row is None:
        raise RuntimeError("Admin user not found — run seed_admin first")
    return str(row[0])


async def main(folder: str) -> None:
    files = sorted(Path(folder).glob("*"))
    files = [f for f in files if f.is_file() and f.suffix.lower() != ".zip"]
    if not files:
        print(f"Нет файлов в {folder}")
        return

    print(f">> RAG engine: ollama/{GENERATOR_MODEL}  emb: ollama/{EMBEDDING_MODEL}")
    adapter = OllamaAdapter(
        base_url=OLLAMA_URL,
        model=GENERATOR_MODEL,
        embedding_model=EMBEDDING_MODEL,
    )
    engine_rag = RAGEngine(llm_adapter=adapter, qdrant_url=QDRANT_URL)

    engine_db = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine_db, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        admin_id = await get_admin_id(session)
        print(f">> Uploaded_by = admin ({admin_id})")

        for f in files:
            print(f"\n>> Загружаю: {f.name}  ({f.stat().st_size / 1024:.1f} KB)")
            doc_id = str(uuid4())

            doc = Document(
                id=doc_id,
                filename=f"{doc_id}{f.suffix.lower()}",
                original_name=f.name,
                file_type=f.suffix.lower().lstrip("."),
                file_size=f.stat().st_size,
                chunk_count=0,
                status=DocumentStatus.PROCESSING,
                uploaded_by=admin_id,
            )
            session.add(doc)
            await session.commit()

            try:
                chunk_count = engine_rag.add_document(str(f), doc_id)
                doc.chunk_count = chunk_count
                doc.status = DocumentStatus.READY
                await session.commit()
                print(f"   OK — {chunk_count} чанков")
            except Exception as e:
                doc.status = DocumentStatus.ERROR
                doc.error_message = str(e)[:500]
                await session.commit()
                print(f"   FAIL — {e}")

    await engine_db.dispose()
    print("\n>> Готово")


if __name__ == "__main__":
    folder = sys.argv[1] if len(sys.argv) > 1 else "/tmp/corpus"
    asyncio.run(main(folder))
