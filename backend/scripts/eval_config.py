"""Чистые (без тяжёлых импортов) хелперы для eval_rag.py — вынесены сюда,
чтобы покрыть юнит-тестами без загрузки mlflow/ragas/llama_index."""

import math


def model_short(model: str) -> str:
    """Короткий слаг модели для run_name и имени кэша: последний сегмент после '/'.

    'deepseek/deepseek-v4-flash' -> 'deepseek-v4-flash'
    'qwen3:1.7b'                 -> 'qwen3:1.7b'
    """
    return model.split("/")[-1]


def samples_cache_filename(
    dataset_source: str, retrieval_mode: str, gen_short: str, top_k: int
) -> str:
    """Имя файла кэша RAG-ответов.

    Ключ включает генератор и top_k — иначе прогоны разных моделей на одном
    (source, mode) затирают друг друга (баг B4: второй/третий генератор
    подхватывал ответы первого).
    """
    return f"samples_{dataset_source}_{retrieval_mode}_{gen_short}_k{top_k}.json"


def build_mlflow_tags(
    *, git_commit, dataset_version, judge_model, purpose, stage, langfuse_session_id
) -> dict:
    """Теги MLflow для фильтрации/воспроизводимости (скилл tracking-experiments)."""
    return {
        "git_commit": git_commit,
        "dataset_version": dataset_version,
        "judge": judge_model,
        "purpose": purpose,
        "stage": stage,
        "langfuse_session_id": langfuse_session_id,
    }


def mean_valid_latency(latencies: list) -> float | None:
    """Среднее по конечным (не-NaN) значениям; None если нет ни одного."""
    valid = [x for x in latencies if isinstance(x, float) and not math.isnan(x)]
    return sum(valid) / len(valid) if valid else None
