#!/usr/bin/env python3
"""
Генерирует тестовый датасет для оценки RAG на основе knowledge graph.

Использует Ragas TestsetGenerator:
  - Подгружает граф из kg.json (создан generate_kg.py).
  - Определяет 3 персонажа (новичок / инструктор / юрист).
  - Конфигурирует распределение типов вопросов
    (single-hop 60% / multi-hop abstract 20% / multi-hop specific 20%).
  - Генерирует TESTSET_SIZE вопросов с эталонными ответами и контекстами.
  - Сохраняет в backend/tests/eval/testset_auto.json.

Запуск:
  OPENROUTER_KEY=$(grep '^OPENROUTER_API_KEY=' .env.eval | cut -d= -f2-)
  docker exec -e OPENROUTER_API_KEY="$OPENROUTER_KEY" \
      faq_rag_llm_bot-backend-1 python -u scripts/generate_testset.py
"""

import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, "/app")

from langchain_ollama import OllamaEmbeddings
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.run_config import RunConfig
from ragas.testset import TestsetGenerator
from ragas.testset.graph import KnowledgeGraph
from ragas.testset.persona import Persona
from ragas.testset.synthesizers.multi_hop.abstract import (
    MultiHopAbstractQuerySynthesizer,
)
from ragas.testset.synthesizers.multi_hop.specific import (
    MultiHopSpecificQuerySynthesizer,
)
from ragas.testset.synthesizers.single_hop.specific import (
    SingleHopSpecificQuerySynthesizer,
)

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434")

GEN_EMB_MODEL = os.environ.get("GEN_EMB_MODEL", "bge-m3")
GEN_PROVIDER = os.environ.get("GEN_PROVIDER", "openrouter")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.environ.get(
    "OPENROUTER_MODEL", "google/gemma-4-31b-it:free"
)
OLLAMA_GEN_MODEL = os.environ.get("OLLAMA_GEN_MODEL", "qwen2.5:7b")

KG_INPUT = Path("/app/tests/eval/kg.json")
TESTSET_OUTPUT = Path("/app/tests/eval/testset_auto.json")

# Сколько вопросов сгенерировать. Учебный пример — 20 хватит для увидеть
# распределения по persona/синтезатору.
TESTSET_SIZE = int(os.environ.get("TESTSET_SIZE", "20"))


PERSONAS = [
    Persona(
        name="novice",
        role_description=(
            "Новичок, никогда не стрелял из боевого оружия. Только что узнал про "
            "практическую стрельбу из YouTube. Говорит без терминов, по-простому. "
            "Часто использует разговорные формулировки: 'как записаться', "
            "'надо ли что-то сдавать', 'долго ли ждать ответа'. Не знает аббревиатур."
        ),
    ),
    Persona(
        name="instructor",
        role_description=(
            "Действующий инструктор ФПСР, ведёт курсы БЕКОСО. Знает термины, "
            "свободно пользуется аббревиатурами (ФПСР, БЕКОСО, РСОО, МКПС, IPSC). "
            "Интересуется процедурными деталями, сроками рассмотрения документов, "
            "ответственностью кандидатов и инструкторов."
        ),
    ),
    Persona(
        name="lawyer",
        role_description=(
            "Юрист ФПСР, проверяет соответствие Положения федеральному "
            "законодательству. Задаёт вопросы со ссылками на ФЗ № 7, № 82, № 150, "
            "№ 329. Проверяет точные формулировки, ссылается на пункты и статьи "
            "Положения и Устава."
        ),
    ),
]


def make_llm():
    if GEN_PROVIDER == "openrouter":
        if not OPENROUTER_API_KEY:
            raise RuntimeError(
                "OPENROUTER_API_KEY не задан — пробрось через env при запуске"
            )
        from langchain_core.rate_limiters import InMemoryRateLimiter
        from langchain_openai import ChatOpenAI

        # OpenRouter лимит free-моделей: 16 RPM. Берём 15 RPM с запасом.
        rate_limiter = InMemoryRateLimiter(
            requests_per_second=15 / 60,
            check_every_n_seconds=0.1,
            max_bucket_size=10,
        )
        return LangchainLLMWrapper(
            ChatOpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=OPENROUTER_API_KEY,
                model=OPENROUTER_MODEL,
                temperature=0,
                timeout=60,
                max_retries=5,
                rate_limiter=rate_limiter,
                default_headers={
                    "HTTP-Referer": "https://github.com/faq-rag-llm-bot",
                    "X-Title": "FAQ RAG testset gen",
                },
            )
        )

    if GEN_PROVIDER == "ollama":
        from langchain_ollama import ChatOllama

        return LangchainLLMWrapper(
            ChatOllama(
                base_url=OLLAMA_URL, model=OLLAMA_GEN_MODEL, temperature=0
            )
        )

    raise ValueError(f"Неизвестный GEN_PROVIDER: {GEN_PROVIDER}")


def main() -> None:
    if not KG_INPUT.exists():
        raise FileNotFoundError(
            f"KG не найден: {KG_INPUT}. Запусти сначала generate_kg.py"
        )

    provider_label = (
        f"openrouter/{OPENROUTER_MODEL}"
        if GEN_PROVIDER == "openrouter"
        else f"ollama/{OLLAMA_GEN_MODEL}"
    )
    print(f">> Generator LLM: {provider_label}")
    print(f">> Embeddings:    ollama/{GEN_EMB_MODEL}")
    print(f">> KG input:      {KG_INPUT}")
    print(f">> Testset size:  {TESTSET_SIZE}")
    print(f">> Personas:      {[p.name for p in PERSONAS]}")
    print()

    kg = KnowledgeGraph.load(str(KG_INPUT))
    print(f">> Узлов в графе: {len(kg.nodes)}")
    print(f">> Рёбер в графе: {len(kg.relationships)}")

    if not kg.relationships:
        print()
        print(
            "[!] В графе 0 рёбер — multi-hop вопросы будут падать или подменяться single-hop."
        )
        print("    Если хочется честный multi-hop — перегенерируй KG.")

    llm = make_llm()
    emb = LangchainEmbeddingsWrapper(
        OllamaEmbeddings(base_url=OLLAMA_URL, model=GEN_EMB_MODEL)
    )

    generator = TestsetGenerator(
        llm=llm,
        embedding_model=emb,
        knowledge_graph=kg,
        persona_list=PERSONAS,
    )

    # NOTE: MultiHopAbstractQuerySynthesizer убран — на нашем KG (только entities_overlap
    # рёбра, без cosine) он падает с "No clusters found". Оставляем single + multi-specific.
    query_distribution = [
        (SingleHopSpecificQuerySynthesizer(llm=llm), 0.6),
        (MultiHopSpecificQuerySynthesizer(llm=llm), 0.4),
    ]

    print("\n>> Генерирую тестовый датасет (LLM-вызовы, ~3 на каждый вопрос)…")
    testset = generator.generate(
        testset_size=TESTSET_SIZE,
        query_distribution=query_distribution,
        run_config=RunConfig(max_workers=1, timeout=300, max_retries=3),
    )

    df = testset.to_pandas()
    TESTSET_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_json(
        str(TESTSET_OUTPUT),
        orient="records",
        force_ascii=False,
        indent=2,
    )

    print(f"\n=== Сгенерированный датасет ===")
    print(f"Размер:       {len(df)}")
    print(f"Файл:         {TESTSET_OUTPUT}")
    print(f"Размер файла: {TESTSET_OUTPUT.stat().st_size / 1024:.1f} KB")

    # Распределение по синтезаторам
    if "synthesizer_name" in df.columns:
        synth_counts = Counter(df["synthesizer_name"])
        print(f"\nПо синтезаторам:")
        for s, c in synth_counts.most_common():
            print(f"  {s:50s}  {c}")

    # Распределение по persona
    persona_col = None
    for cand in ("persona", "persona_name"):
        if cand in df.columns:
            persona_col = cand
            break
    if persona_col:
        # persona может быть dict / Persona-объект — приведём к строке
        def to_name(x):
            if isinstance(x, dict):
                return x.get("name", str(x))
            return getattr(x, "name", str(x))

        pers_counts = Counter(df[persona_col].map(to_name))
        print(f"\nПо персонам:")
        for p, c in pers_counts.most_common():
            print(f"  {p:20s}  {c}")

    # 3 примера для глаза
    print(f"\nПервые 3 вопроса (для проверки на глаз):")
    for i, row in df.head(3).iterrows():
        print(f"\n  --- {i+1} ---")
        print(f"  Q:   {row.get('user_input', '?')}")
        ref = str(row.get("reference", "?"))
        print(f"  Ref: {ref[:200]}{'…' if len(ref) > 200 else ''}")


if __name__ == "__main__":
    main()
