#!/usr/bin/env python3
"""
Ragas + MLflow evaluation of the existing RAG pipeline.

Прогоняет маленький golden-датасет через текущий RAGEngine, считает
ragas-метрики (faithfulness, answer_relevancy, context_precision/recall),
логирует параметры, метрики и таблицу результатов в локальный MLflow.

Запуск (внутри backend контейнера, где есть Python 3.11 + llama-index):

    docker exec -it faq_rag_llm_bot-backend-1 python scripts/eval_rag.py

UI MLflow (отдельно, один раз):

    docker exec -d faq_rag_llm_bot-backend-1 \
        mlflow ui --backend-store-uri sqlite:////app/mlflow.db \
                  --host 0.0.0.0 --port 5000

    # затем https://localhost:5000 (нужно пробросить порт — см. status.md)
"""

import os
import sys
from datetime import datetime

sys.path.insert(0, "/app")

import mlflow
from langchain_ollama import ChatOllama, OllamaEmbeddings
from llama_index.core import PromptTemplate
from ragas import EvaluationDataset, evaluate
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import (
    AnswerRelevancy,
    Faithfulness,
    LLMContextPrecisionWithReference,
    LLMContextRecall,
)
from ragas.run_config import RunConfig

from app.core.llm.ollama import OllamaAdapter
from app.core.observability import (
    flush as obs_flush,
    init_observability,
    langchain_callbacks,
    prompt_hash,
    push_scores,
    trace_context,
)
from app.core.rag.engine import SYSTEM_PROMPT
from app.core.rag.retriever import QdrantRetriever

sys.path.insert(0, "/app/scripts")
from eval_config import build_mlflow_tags, model_short, samples_cache_filename

# Hybrid retriever импортируем лениво (только если HYBRID=true) — fastembed
# подгружает модель ~80 MB при импорте.

import json
from pathlib import Path

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434")
QDRANT_URL = os.environ.get("QDRANT_URL", "http://qdrant:6333")
MLFLOW_URI = os.environ.get("MLFLOW_URI", "sqlite:////app/mlflow.db")

# Hybrid retrieval (dense + sparse + RRF) или dense-only (default).
# Если HYBRID=true → используем HybridQdrantRetriever (коллекция documents_hybrid).
HYBRID = os.environ.get("HYBRID", "false").lower() in {"1", "true", "yes"}
RETRIEVAL_MODE = "hybrid" if HYBRID else "dense"

# Источник датасета: "manual" — ручные 10 вопросов ниже,
#                    "json"   — загружается из DATASET_PATH (по умолчанию testset_auto.json).
DATASET_SOURCE = os.environ.get("DATASET_SOURCE", "manual")
DATASET_PATH = os.environ.get("DATASET_PATH", "/app/tests/eval/testset_auto.json")

# Генератор RAG: провайдер через env-флаг.
# - ollama: локальный (dev), но qwen3:1.7b reasoning-модель регулярно зависает
# - openrouter: модель из backend/models.env (GEN_MODEL), стабильно
GENERATOR_PROVIDER = os.environ.get("GENERATOR_PROVIDER", "ollama")

OLLAMA_GEN_MODEL = os.environ.get("OLLAMA_GEN_MODEL", "qwen3:1.7b")
# Модель генератора (OpenRouter) — из backend/models.env через Makefile (env).
# Своего дефолта НЕТ: нет env → падаем в make_rag_llm.
OPENROUTER_GEN_MODEL = os.environ.get("OPENROUTER_GEN_MODEL", "")
EMBEDDING_MODEL = "bge-m3"
TOP_K = 5

# Судья — провайдер выбираем env-флагом.
JUDGE_PROVIDER = os.environ.get("JUDGE_PROVIDER", "openrouter")

# Для OpenRouter:
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
# Модель судьи — из backend/models.env через Makefile (env). Своего дефолта НЕТ:
# нет env → падаем в make_judge_llm (никакой тихо подхваченной стухшей модели).
OPENROUTER_JUDGE_MODEL = os.environ.get("OPENROUTER_JUDGE_MODEL", "")

# Для Ollama (fallback):
OLLAMA_JUDGE_MODEL = os.environ.get("OLLAMA_JUDGE_MODEL", "qwen2.5:7b")

# Langfuse observability (A3). Выключен по умолчанию → трейсы не шлём.
# Включить прогон с трейсами: make eval-dense LANGFUSE_ENABLED=true
LANGFUSE_ENABLED = os.environ.get("LANGFUSE_ENABLED", "false").lower() in {"1", "true", "yes"}
GIT_COMMIT = os.environ.get("GIT_COMMIT", "unknown")


def make_judge_llm():
    if JUDGE_PROVIDER == "openrouter":
        if not OPENROUTER_API_KEY:
            raise RuntimeError(
                "OPENROUTER_API_KEY не задан — пробрось через env при запуске docker exec"
            )
        if not OPENROUTER_JUDGE_MODEL:
            raise RuntimeError(
                "OPENROUTER_JUDGE_MODEL не задан — задай JUDGE_MODEL в backend/models.env "
                "(запуск через make) или пробрось env вручную"
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
                model=OPENROUTER_JUDGE_MODEL,
                temperature=0,
                timeout=60,
                max_retries=5,
                rate_limiter=rate_limiter,
                default_headers={
                    "HTTP-Referer": "https://github.com/faq-rag-llm-bot",
                    "X-Title": "FAQ RAG eval",
                },
            )
        )

    if JUDGE_PROVIDER == "ollama":
        # Ограничиваем num_ctx — иначе qwen2.5:7b резервирует огромный KV cache
        # и Docker on Mac выкидывает по OOM.
        return LangchainLLMWrapper(
            ChatOllama(
                base_url=OLLAMA_URL,
                model=OLLAMA_JUDGE_MODEL,
                temperature=0,
                num_ctx=8192,
                num_predict=1024,
            )
        )

    raise ValueError(f"Неизвестный JUDGE_PROVIDER: {JUDGE_PROVIDER}")

GOLDEN_DATASET = [
    {
        "question": "Что такое БЕКОСО и где найти список инструкторов ФПСР?",
        "reference": (
            "БЕКОСО — это курсы безопасного и квалифицированного обращения с оружием, "
            "которые кандидат в члены Федерации обязан пройти у инструктора ФПСР. "
            "Список инструкторов ФПСР опубликован на сайте Федерации https://ipsc.ru/."
        ),
    },
    {
        "question": "В каких случаях инструктор ФПСР обязан отстранить кандидата от курса БЕКОСО?",
        "reference": (
            "Инструктор обязан прекратить обучение, если кандидат демонстрирует систематическое "
            "пренебрежение мерами безопасности, создавая угрозу безопасности другим обучающимся, "
            "инструкторам и третьим лицам, либо систематически не выполняет команды инструктора."
        ),
    },
    {
        "question": "Кто принимает решение о приёме физического лица в члены ФПСР?",
        "reference": (
            "Решение о приёме (непринятии) физического лица в члены Федерации принимает "
            "Президент Федерации путём подтверждения или отклонения электронного заявления "
            "(анкеты) кандидата в личном кабинете."
        ),
    },
    {
        "question": "В какой срок Президент Федерации обязан принять решение о вступлении кандидата?",
        "reference": (
            "Президент Федерации принимает решение не позднее конца месяца, следующего за "
            "месяцем получения электронного заявления (анкеты) от кандидата в члены Федерации."
        ),
    },
    {
        "question": "Каким большинством принимается решение об исключении из членов Федерации?",
        "reference": (
            "Решение об исключении считается принятым, если за него проголосовало не менее "
            "2/3 членов Исполнительного комитета Федерации, участвовавших в заседании."
        ),
    },
    {
        "question": "Что происходит со взносами члена Федерации при его исключении?",
        "reference": (
            "При исключении из членов Федерации по решению Исполнительного комитета у лица "
            "не возникает права на возврат уплаченных взносов."
        ),
    },
    {
        "question": "Что происходит с членством в IPSC при принятии в члены ФПСР?",
        "reference": (
            "Принятие физического лица в члены ФПСР автоматически делает его членом "
            "(участником) Международной Конфедерации Практической Стрельбы (IPSC). "
            "Федерация обязуется обеспечивать поддержание этого статуса, в том числе через "
            "оплату необходимых взносов."
        ),
    },
    {
        "question": "Кто не может быть членом ФПСР?",
        "reference": (
            "Не могут быть членами Федерации, в частности: лица, содержащиеся в местах "
            "лишения свободы по приговору суда; лица, в отношении которых судом установлены "
            "признаки экстремистской деятельности; лица, признанные судом недееспособными; "
            "общественные объединения с приостановленной деятельностью по антиэкстремистскому "
            "законодательству; лица из перечня по ФЗ № 115-ФЗ о противодействии легализации."
        ),
    },
    {
        "question": "Какие нормативные акты лежат в основе Положения о членстве ФПСР?",
        "reference": (
            "Положение принято в соответствии с Федеральным законом № 7-ФЗ «О некоммерческих "
            "организациях», № 82-ФЗ «Об общественных объединениях», № 150-ФЗ «Об оружии», "
            "№ 329-ФЗ «О физической культуре и спорте в Российской Федерации», иными "
            "нормативно-правовыми актами РФ и Уставом Федерации."
        ),
    },
    {
        "question": "По каким основаниям Президент Федерации может исключить члена ФПСР?",
        "reference": (
            "Президент Федерации принимает решение об исключении из членов Федерации по "
            "двум основаниям: в связи с неуплатой членских взносов в течение 1 года и по "
            "собственному желанию члена Федерации."
        ),
    },
]


def load_dataset() -> list[dict]:
    """
    Возвращает список пар {question, reference} в едином виде.
    Источник управляется env-флагом DATASET_SOURCE.
    """
    if DATASET_SOURCE == "manual":
        return [
            {"question": item["question"], "reference": item["reference"]}
            for item in GOLDEN_DATASET
        ]

    if DATASET_SOURCE == "json":
        path = Path(DATASET_PATH)
        if not path.exists():
            raise FileNotFoundError(f"Датасет не найден: {path}")
        with open(path, encoding="utf-8") as f:
            rows = json.load(f)
        # Поля из Ragas testset: user_input, reference, reference_contexts, synthesizer_name
        return [
            {
                "question": r["user_input"],
                "reference": r.get("reference", ""),
                "synthesizer_name": r.get("synthesizer_name", ""),
            }
            for r in rows
        ]

    raise ValueError(f"Неизвестный DATASET_SOURCE: {DATASET_SOURCE}")


def run_rag(question: str, retriever, llm) -> tuple[str, list[str]]:
    """Прогоняет вопрос через RAG и возвращает (ответ, список текстов чанков)."""
    index = retriever.get_index()
    query_engine = index.as_query_engine(
        llm=llm,
        similarity_top_k=TOP_K,
        text_qa_template=PromptTemplate(SYSTEM_PROMPT),
    )
    response = query_engine.query(question)
    contexts = [node.text for node in response.source_nodes]
    return str(response), contexts


def make_rag_llm():
    """Создаёт LLM для RAG-генерации (отвечает на вопросы пользователя)."""
    if GENERATOR_PROVIDER == "ollama":
        # qwen3:1.7b reasoning-модель — урезаем num_ctx чтобы избежать OOM на Mac,
        # и num_predict чтобы reasoning не уходил в бесконечный thinking.
        from llama_index.llms.ollama import Ollama as _Ollama
        return _Ollama(
            base_url=OLLAMA_URL,
            model=OLLAMA_GEN_MODEL,
            temperature=0.1,
            request_timeout=600.0,
            context_window=8192,
            additional_kwargs={"num_ctx": 8192, "num_predict": 1024},
        )

    if GENERATOR_PROVIDER == "openrouter":
        if not OPENROUTER_API_KEY:
            raise RuntimeError("OPENROUTER_API_KEY не задан")
        if not OPENROUTER_GEN_MODEL:
            raise RuntimeError(
                "OPENROUTER_GEN_MODEL не задан — задай GEN_MODEL в backend/models.env "
                "(запуск через make) или пробрось env вручную"
            )
        from llama_index.llms.openai_like import OpenAILike
        return OpenAILike(
            api_base="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY,
            model=OPENROUTER_GEN_MODEL,
            is_chat_model=True,
            temperature=0.1,
            timeout=300,
            max_retries=5,
            additional_kwargs={"max_tokens": 1024},
            default_headers={
                "HTTP-Referer": "https://github.com/faq-rag-llm-bot",
                "X-Title": "FAQ RAG eval (generator)",
            },
        )

    raise ValueError(f"Неизвестный GENERATOR_PROVIDER: {GENERATOR_PROVIDER}")


def main() -> None:
    gen_label = (
        f"openrouter/{OPENROUTER_GEN_MODEL}"
        if GENERATOR_PROVIDER == "openrouter"
        else f"ollama/{OLLAMA_GEN_MODEL}"
    )
    print(f">> RAG generator: {gen_label}  emb: ollama/{EMBEDDING_MODEL}")
    rag_llm = make_rag_llm()

    init_observability(
        LANGFUSE_ENABLED,
        public_key=os.environ.get("LANGFUSE_PUBLIC_KEY"),
        secret_key=os.environ.get("LANGFUSE_SECRET_KEY"),
        host=os.environ.get("LANGFUSE_HOST"),
    )
    gen_model_name = OPENROUTER_GEN_MODEL if GENERATOR_PROVIDER == "openrouter" else OLLAMA_GEN_MODEL
    judge_model_name = OPENROUTER_JUDGE_MODEL if JUDGE_PROVIDER == "openrouter" else OLLAMA_JUDGE_MODEL
    # Человекочитаемый session_id: что(eval)-как(mode)-чем(генератор)-когда(timestamp).
    # Timestamp даёт и уникальность между прогонами, и понятность. Связь с MLflow —
    # этот id логируется как MLflow-param langfuse_session_id (см. ниже).
    lf_session_id = (
        f"eval-{RETRIEVAL_MODE}-{gen_model_name.split('/')[-1]}"
        f"-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    )

    # Embeddings всегда локальные через Ollama (bge-m3) — быстро, без API-нагрузки.
    rag_adapter = OllamaAdapter(
        base_url=OLLAMA_URL,
        model=OLLAMA_GEN_MODEL,  # не используется в RAG здесь, но нужен в адаптере
        embedding_model=EMBEDDING_MODEL,
    )
    rag_emb = rag_adapter.get_embedding_model()

    print(f">> Qdrant retriever: {QDRANT_URL}  mode={RETRIEVAL_MODE}")
    if HYBRID:
        sys.path.insert(0, "/app/scripts")
        from _hybrid_retriever import HybridQdrantRetriever
        retriever = HybridQdrantRetriever(QDRANT_URL, rag_emb)
    else:
        retriever = QdrantRetriever(QDRANT_URL, rag_emb)

    judge_label = (
        f"openrouter/{OPENROUTER_JUDGE_MODEL}"
        if JUDGE_PROVIDER == "openrouter"
        else f"ollama/{OLLAMA_JUDGE_MODEL}"
    )
    print(f">> Ragas judge: {judge_label}")
    judge_llm = make_judge_llm()
    judge_emb = LangchainEmbeddingsWrapper(
        OllamaEmbeddings(base_url=OLLAMA_URL, model=EMBEDDING_MODEL)
    )

    items = load_dataset()
    print(f"\n>> Источник датасета: {DATASET_SOURCE} ({len(items)} вопросов)")

    # Кэш промежуточных RAG-результатов — чтобы при повторных запусках судьи
    # не перепрогонять долгие LLM-генерации.
    gen_short = model_short(
        OPENROUTER_GEN_MODEL if GENERATOR_PROVIDER == "openrouter" else OLLAMA_GEN_MODEL
    )
    samples_cache_path = Path(
        "/app/tests/eval/"
        + samples_cache_filename(DATASET_SOURCE, RETRIEVAL_MODE, gen_short, TOP_K)
    )
    if samples_cache_path.exists() and os.environ.get("SKIP_CACHE") != "true":
        print(f">> Загружаю кэш RAG-ответов: {samples_cache_path}")
        with open(samples_cache_path, encoding="utf-8") as f:
            cached = json.load(f)
        samples = cached["samples"]
        synthesizers = cached.get("synthesizers", [""] * len(samples))
        # Из кэша генерация не прогонялась → трейсов генератора нет.
        # Для Langfuse-прогона запускай свежим (SKIP_CACHE=true или удали кэш).
        lf_trace_ids = [None] * len(samples)
        print(f"   {len(samples)} samples (skip RAG phase)")
    else:
        print(f">> Прогон RAG на {len(items)} вопросах...")
        samples = []
        synthesizers = []
        lf_trace_ids = []
        failed_indices = []
        for i, item in enumerate(items, 1):
            q_preview = item["question"][:80] + ("…" if len(item["question"]) > 80 else "")
            print(f"   [{i}/{len(items)}] {q_preview}")
            with trace_context(
                user_id=f"eval:{item.get('synthesizer_name', '')}:{i}",
                session_id=lf_session_id,
                tags=[RETRIEVAL_MODE],
                metadata={
                    "generator_model": gen_model_name,
                    "judge_model": judge_model_name,
                    "top_k": TOP_K,
                    "git_commit": GIT_COMMIT,
                    "prompt_hash": prompt_hash(SYSTEM_PROMPT),
                },
            ) as trace:
                try:
                    answer, contexts = run_rag(item["question"], retriever, rag_llm)
                except Exception as e:
                    print(f"      [!] FAIL: {type(e).__name__}: {str(e)[:120]}")
                    failed_indices.append(i)
                    answer = "[Ошибка генерации: вопрос не отвечен]"
                    contexts = []
                trace.update(metadata={"chunks": len(contexts)})
            lf_trace_ids.append(trace.id)
            samples.append(
                {
                    "user_input": item["question"],
                    "retrieved_contexts": contexts,
                    "response": answer,
                    "reference": item["reference"],
                }
            )
            synthesizers.append(item.get("synthesizer_name", ""))

        if failed_indices:
            print(f"\n[!] Упали {len(failed_indices)} вопросов: {failed_indices}")
            print("    Они будут оценены с пустым контекстом / failure-ответом.")

        # Сохраняем кэш — судья теперь может перезапускаться без RAG.
        samples_cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(samples_cache_path, "w", encoding="utf-8") as f:
            json.dump(
                {"samples": samples, "synthesizers": synthesizers},
                f,
                ensure_ascii=False,
                indent=2,
            )
        print(f"\n>> RAG-кэш сохранён: {samples_cache_path}")

    dataset = EvaluationDataset.from_list(samples)

    mlflow.set_tracking_uri(MLFLOW_URI)
    mlflow.set_experiment("ragas-eval")

    judge_short = (
        OPENROUTER_JUDGE_MODEL.split("/")[-1]
        if JUDGE_PROVIDER == "openrouter"
        else OLLAMA_JUDGE_MODEL
    )
    run_name = f"{DATASET_SOURCE}-{RETRIEVAL_MODE}-{gen_short}-judge-{judge_short}-k{TOP_K}"
    with mlflow.start_run(run_name=run_name) as run:
        mlflow.log_params(
            {
                "generator_provider": GENERATOR_PROVIDER,
                "generator_model": (
                    OPENROUTER_GEN_MODEL
                    if GENERATOR_PROVIDER == "openrouter"
                    else OLLAMA_GEN_MODEL
                ),
                "embedding_model": EMBEDDING_MODEL,
                "judge_provider": JUDGE_PROVIDER,
                "judge_model": (
                    OPENROUTER_JUDGE_MODEL
                    if JUDGE_PROVIDER == "openrouter"
                    else OLLAMA_JUDGE_MODEL
                ),
                "top_k": TOP_K,
                "retrieval_mode": RETRIEVAL_MODE,
                "dataset_source": DATASET_SOURCE,
                "dataset_path": DATASET_PATH if DATASET_SOURCE == "json" else "<inline>",
                "dataset_size": len(items),
                "langfuse_session_id": lf_session_id,
            }
        )

        print("\n>> Ragas evaluate (это самая долгая часть — LLM-судья по каждой паре)...")
        # max_workers=1: Ollama сериализует запросы к одной модели, параллелизм
        # на клиенте только создаёт очередь и срабатывают таймауты.
        # timeout=600: qwen2.5:7b на CPU отвечает медленно, дефолтных 60с не хватает.
        result = evaluate(
            dataset=dataset,
            metrics=[
                Faithfulness(),
                AnswerRelevancy(),
                LLMContextPrecisionWithReference(),
                LLMContextRecall(),
            ],
            llm=judge_llm,
            embeddings=judge_emb,
            run_config=RunConfig(max_workers=1, timeout=600, max_retries=3),
            show_progress=True,
            # NaN на упавших Job-ах — лучше чем потерять весь прогон.
            raise_exceptions=False,
            # Langfuse-колбэк судьи (пусто при выключенном флаге) → трейсы+cost судьи.
            callbacks=langchain_callbacks(),
        )

        df = result.to_pandas()
        # Добавим synthesizer как колонку для срезов (если auto-датасет).
        if DATASET_SOURCE == "json" and synthesizers and len(synthesizers) == len(df):
            df["synthesizer"] = synthesizers
        out_csv = f"/tmp/eval_results_{DATASET_SOURCE}.csv"
        df.to_csv(out_csv, index=False)
        mlflow.log_artifact(out_csv)

        numeric_cols = [c for c in df.columns if df[c].dtype.kind in "fi"]
        for col in numeric_cols:
            mean_val = df[col].dropna().mean()
            if mean_val == mean_val:
                mlflow.log_metric(f"mean_{col}", float(mean_val))

        # Срез средних метрик по синтезатору (только для auto-датасета)
        if DATASET_SOURCE == "json" and "synthesizer" in df.columns:
            for synth, sub in df.groupby("synthesizer"):
                synth_short = synth.replace("_synthesizer", "")[:30]
                for col in numeric_cols:
                    m = sub[col].dropna().mean()
                    if m == m:
                        mlflow.log_metric(f"by_synth__{synth_short}__{col}", float(m))

        print("\n=== Сводка по метрикам ===")
        numeric_cols = [c for c in df.columns if df[c].dtype.kind in "fi"]
        for col in numeric_cols:
            print(f"  {col:35s} mean = {df[col].dropna().mean():.3f}")

        # Ragas-метрики по каждому вопросу → Scores на соответствующий трейс генератора.
        # Только для свежего прогона (из кэша trace_id нет — см. кэш-ветку выше).
        if any(lf_trace_ids) and len(lf_trace_ids) == len(df):
            for idx, tid in enumerate(lf_trace_ids):
                if not tid:
                    continue
                row = df.iloc[idx]
                push_scores(tid, {c: row[c] for c in numeric_cols})
            print(">> Scores отправлены в Langfuse")
        obs_flush()

        print(f"\n>> MLflow run_id: {run.info.run_id}")
        print(f">> CSV артефакт: {out_csv}")
        print(">> Запусти UI: mlflow ui --backend-store-uri sqlite:////app/mlflow.db")


if __name__ == "__main__":
    main()
