#!/usr/bin/env python3
"""
Создаёт hybrid-коллекцию (documents_hybrid) с dense + sparse векторами и
загружает в неё те же 3 PDF, что и обычный ingest.

Используется тот же DocumentLoader (одинаковый chunking), что и для dense
коллекции — чтобы единственным отличием между двумя коллекциями было
наличие/отсутствие sparse-векторов.

Запуск (внутри backend контейнера):
    docker exec faq_rag_llm_bot-backend-1 python -u scripts/ingest_hybrid.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, "/app")
sys.path.insert(0, "/app/scripts")

from app.core.llm.ollama import OllamaAdapter
from app.core.rag.loader import DocumentLoader

from _hybrid_retriever import COLLECTION_NAME, HybridQdrantRetriever

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434")
QDRANT_URL = os.environ.get("QDRANT_URL", "http://qdrant:6333")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "bge-m3")

CORPUS_DIR = Path(os.environ.get("CORPUS_DIR", "/tmp/corpus"))


def main() -> None:
    files = sorted(f for f in CORPUS_DIR.glob("*") if f.is_file() and f.suffix.lower() != ".zip")
    if not files:
        print(f"Нет файлов в {CORPUS_DIR}")
        return

    print(f">> Embeddings: ollama/{EMBEDDING_MODEL}")
    print(f">> Qdrant:     {QDRANT_URL}")
    print(f">> Коллекция:  {COLLECTION_NAME}")
    print()

    adapter = OllamaAdapter(
        base_url=OLLAMA_URL,
        model="dummy",  # не используется — нам нужен только embedding_model
        embedding_model=EMBEDDING_MODEL,
    )
    emb = adapter.get_embedding_model()
    retriever = HybridQdrantRetriever(QDRANT_URL, emb)

    loader = DocumentLoader()
    for f in files:
        print(f">> Парсю + индексирую: {f.name} ({f.stat().st_size / 1024:.1f} KB)")
        docs = loader.load_file(str(f))
        nodes = loader.chunk_documents(docs)
        for node in nodes:
            node.metadata.setdefault("filename", f.name)
            node.metadata.setdefault("file_type", f.suffix.lower().lstrip("."))
        doc_id = f"hybrid-{f.stem}"
        retriever.add_documents(nodes, doc_id)
        print(f"   {len(nodes)} чанков → {COLLECTION_NAME}")

    print("\n>> Готово")


if __name__ == "__main__":
    main()
