#!/usr/bin/env python3
"""
Строит Ragas Knowledge Graph для последующей генерации тестового датасета.

Что делает:
  1. Берёт PDF из CORPUS_FILES, разбивает на чанки тем же DocumentLoader,
     что и продакшен-RAG (consistency: тестируем то же что использует пользователь).
  2. Заворачивает чанки в LangchainDocuments → Node типа CHUNK.
  3. Прогоняет default_transforms — серия LLM-вызовов, обогащающих каждый узел
     (summary, headlines, NER-entities, keyphrases, embedding).
  4. Строит рёбра между узлами по cosine/jaccard/overlap.
  5. Сохраняет граф в KG_OUTPUT (JSON).
  6. Печатает статистику.

Время:
  - Локально на qwen2.5:7b: ~10–15 мин для одного "Положения о членстве" (31 чанк).
  - Через OpenRouter (Haiku/GPT-4o-mini): 1–2 мин.

Запуск:
  docker exec -e KG_LLM_MODEL=qwen3:1.7b faq_rag_llm_bot-backend-1 \
      python -u scripts/generate_kg.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, "/app")

from langchain_core.documents import Document as LangchainDocument
from langchain_ollama import OllamaEmbeddings
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.run_config import RunConfig
from ragas.testset.graph import KnowledgeGraph, Node, NodeType
from ragas.testset.transforms import apply_transforms, default_transforms

from app.core.rag.loader import DocumentLoader

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434")

# Эмбеддинги всегда локальные через bge-m3 — быстро, без расходов на API,
# и совпадают с тем что использует прод-RAG (важно для consistency).
KG_EMB_MODEL = os.environ.get("KG_EMB_MODEL", "bge-m3")

# Провайдер LLM для transforms: "openrouter" или "ollama".
KG_PROVIDER = os.environ.get("KG_PROVIDER", "openrouter")

# Для OpenRouter:
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
# Модель KG/testset — из backend/models.env через Makefile (env). Своего дефолта НЕТ:
# нет env → падаем в make_llm (никакой тихо подхваченной стухшей модели).
OPENROUTER_KG_MODEL = os.environ.get("OPENROUTER_KG_MODEL", "")

# Для Ollama (fallback / оффлайн):
OLLAMA_KG_MODEL = os.environ.get("OLLAMA_KG_MODEL", "qwen2.5:7b")

# Корпус берём из /tmp/corpus/ — всё что туда положено (ingest читает то же).
# Битые PDF должны быть переложены в /tmp/corpus_skipped/.
CORPUS_DIR = Path(os.environ.get("CORPUS_DIR", "/tmp/corpus"))
CORPUS_FILES = sorted(
    str(p) for p in CORPUS_DIR.glob("*")
    if p.is_file() and p.suffix.lower() in {".pdf", ".txt", ".md", ".html", ".docx", ".xlsx"}
)

# Ограничение чанков на документ. None = без лимита.
_max = os.environ.get("MAX_CHUNKS_PER_DOC")
MAX_CHUNKS_PER_DOC: int | None = int(_max) if _max else None

KG_OUTPUT = Path("/app/tests/eval/kg.json")


def make_llm():
    """Создаёт LLM-обёртку под выбранный провайдер."""
    if KG_PROVIDER == "openrouter":
        if not OPENROUTER_API_KEY:
            raise RuntimeError(
                "OPENROUTER_API_KEY не задан — пробрось через env при запуске docker exec"
            )
        if not OPENROUTER_KG_MODEL:
            raise RuntimeError(
                "OPENROUTER_KG_MODEL не задан — задай KG_MODEL в backend/models.env "
                "(запуск через make) или пробрось env вручную"
            )
        from langchain_openai import ChatOpenAI

        return LangchainLLMWrapper(
            ChatOpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=OPENROUTER_API_KEY,
                model=OPENROUTER_KG_MODEL,
                temperature=0,
                timeout=60,
                max_retries=2,
                default_headers={
                    "HTTP-Referer": "https://github.com/faq-rag-llm-bot",
                    "X-Title": "FAQ RAG eval",
                },
            )
        )

    if KG_PROVIDER == "ollama":
        from langchain_ollama import ChatOllama

        return LangchainLLMWrapper(
            ChatOllama(base_url=OLLAMA_URL, model=OLLAMA_KG_MODEL, temperature=0)
        )

    raise ValueError(f"Неизвестный KG_PROVIDER: {KG_PROVIDER}")


def load_chunks() -> tuple[list[LangchainDocument], int]:
    """Парсит PDF, разбивает на чанки тем же DocumentLoader, что и прод-RAG."""
    loader = DocumentLoader()
    lc_docs: list[LangchainDocument] = []

    for file_path in CORPUS_FILES:
        path = Path(file_path)
        print(f">> Парсю: {path.name}")
        docs = loader.load_file(str(path))
        nodes = loader.chunk_documents(docs)

        if MAX_CHUNKS_PER_DOC is not None and len(nodes) > MAX_CHUNKS_PER_DOC:
            print(f"   {len(nodes)} чанков → урезаю до {MAX_CHUNKS_PER_DOC}")
            nodes = nodes[:MAX_CHUNKS_PER_DOC]
        else:
            print(f"   {len(nodes)} чанков")

        for node in nodes:
            lc_docs.append(
                LangchainDocument(
                    page_content=node.text,
                    metadata={
                        **(node.metadata or {}),
                        "source_file": path.name,
                    },
                )
            )

    return lc_docs, len(lc_docs)


def main() -> None:
    provider_label = (
        f"openrouter/{OPENROUTER_KG_MODEL}"
        if KG_PROVIDER == "openrouter"
        else f"ollama/{OLLAMA_KG_MODEL}"
    )
    print(f">> KG LLM:        {provider_label}")
    print(f">> KG embeddings: ollama/{KG_EMB_MODEL}")
    print(f">> Корпус:        {[Path(f).name for f in CORPUS_FILES]}")
    print()

    docs, n = load_chunks()
    print(f"\n>> Всего узлов будет: {n}")

    # Создаём узлы типа DOCUMENT — default_transforms в Ragas ожидает именно их:
    # сам сделает HeadlinesExtractor → HeadlineSplitter → CHUNK → Summary →
    # Embedding → Themes → NER → relationship builders.
    # Если делать CHUNK сразу, многие трансформы molcha skipаются.
    kg = KnowledgeGraph()
    for doc in docs:
        kg.nodes.append(
            Node(
                type=NodeType.DOCUMENT,
                properties={
                    "page_content": doc.page_content,
                    "document_metadata": doc.metadata,
                },
            )
        )

    print(">> Поднимаю LLM/Embeddings…")
    llm = make_llm()
    emb = LangchainEmbeddingsWrapper(
        OllamaEmbeddings(base_url=OLLAMA_URL, model=KG_EMB_MODEL)
    )

    print(">> Прогоняю default_transforms (это самая долгая часть — много LLM-вызовов)…")
    # max_workers=1: Ollama сериализует запросы, параллелизм только тормозит.
    transforms = default_transforms(documents=docs, llm=llm, embedding_model=emb)
    apply_transforms(
        kg,
        transforms,
        run_config=RunConfig(max_workers=1, timeout=600, max_retries=3),
    )

    # --- статистика ---
    from collections import Counter

    print(f"\n=== Knowledge Graph готов ===")
    print(f"Узлов:  {len(kg.nodes)}")
    print(f"Рёбер:  {len(kg.relationships)}")

    rel_types = Counter(r.type for r in kg.relationships)
    if rel_types:
        print("\nТипы рёбер:")
        for t, c in rel_types.most_common():
            print(f"  {t:40s}  {c}")

    # Топ сущностей по частоте (после NER-трансформа)
    all_entities = []
    for node in kg.nodes:
        ents = node.properties.get("entities", []) or []
        all_entities.extend(ents if isinstance(ents, list) else [])
    if all_entities:
        ent_counts = Counter(all_entities)
        print(f"\nТоп-10 entities (всего разных: {len(ent_counts)}):")
        for ent, c in ent_counts.most_common(10):
            print(f"  {ent}  ×{c}")

    # Топ keyphrases
    all_keyphrases = []
    for node in kg.nodes:
        kps = node.properties.get("keyphrases", []) or []
        all_keyphrases.extend(kps if isinstance(kps, list) else [])
    if all_keyphrases:
        kp_counts = Counter(all_keyphrases)
        print(f"\nТоп-10 keyphrases:")
        for kp, c in kp_counts.most_common(10):
            print(f"  {kp}  ×{c}")

    # --- сохранение ---
    KG_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    kg.save(str(KG_OUTPUT))
    print(f"\n>> Граф сохранён: {KG_OUTPUT}")
    print(f">> Размер файла:  {KG_OUTPUT.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
