"""Единственная точка Langfuse-логики (задача A3).

Вариант C: нативные интеграции ловят токены/стоимость (генератор через
OpenInference-инструментор LlamaIndex, судья через LangChain CallbackHandler в
Ragas), а эта обёртка владеет идентичностью трейса (user_id/session_id/tags/
metadata) и вешает Scores. Флаг LANGFUSE_ENABLED выключен → всё no-op, ноль сети.

API под langfuse SDK v3 (проверено на 3.15): client.start_as_current_span,
client.update_current_trace, client.get_current_trace_id, client.create_score,
client.flush. NB: в v3 langfuse.llama_index удалён → генератор инструментируется
через openinference-instrumentation-llama-index.

Спека: docs/superpowers/specs/2026-07-15-langfuse-observability-design.md
"""
import hashlib
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)

_client = None       # Langfuse client или None
_enabled = False
_lf_callback = None  # LangChain CallbackHandler (судья) или None


def prompt_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]


def init_observability(enabled, public_key=None, secret_key=None, host=None) -> bool:
    """Идемпотентно. enabled=False → no-op. Ошибка инициализации → тихо выключаемся
    (observability не должна ронять систему). Возвращает фактический флаг."""
    global _client, _enabled, _lf_callback
    if not enabled:
        _enabled = False
        return False
    if _client is not None:
        return True
    try:
        from langfuse import Langfuse
        from langfuse.langchain import CallbackHandler
        from openinference.instrumentation.llama_index import LlamaIndexInstrumentor

        _client = Langfuse(public_key=public_key, secret_key=secret_key, host=host)
        LlamaIndexInstrumentor().instrument()  # LlamaIndex → OTEL-спаны в Langfuse
        _lf_callback = CallbackHandler()
        _enabled = True
        logger.info("Langfuse observability enabled (host=%s)", host)
        return True
    except Exception as exc:
        logger.warning("Langfuse init failed → observability disabled: %s", exc)
        _client = None
        _enabled = False
        return False


class TraceHandle:
    """Ручка на текущий трейс. `id` захвачен внутри контекста (доступен и после
    выхода из него — нужно для привязки Scores в eval). `update` дописывает
    метаданные в трейс (вызывать внутри активного trace_context)."""

    def __init__(self, trace_id=None):
        self._id = trace_id

    @property
    def id(self):
        return self._id

    def update(self, metadata=None):
        if _enabled and _client and metadata:
            _client.update_current_trace(metadata=metadata)


@contextmanager
def trace_context(user_id=None, session_id=None, tags=None, metadata=None):
    if not _enabled or _client is None:
        yield TraceHandle(None)
        return
    with _client.start_as_current_span(name="rag-query"):
        _client.update_current_trace(
            user_id=user_id,
            session_id=session_id,
            tags=tags or [],
            metadata=metadata or {},
        )
        yield TraceHandle(_client.get_current_trace_id())


def push_scores(trace_id, scores):
    """Вешает числовые Scores на трейс. None/NaN пропускаются."""
    if not (_enabled and _client and trace_id):
        return
    for name, value in scores.items():
        if value is None or (isinstance(value, float) and value != value):  # None / NaN
            continue
        _client.create_score(trace_id=trace_id, name=name, value=float(value))


def langchain_callbacks():
    """Колбэки для ragas.evaluate(callbacks=...). Пусто при выключенном флаге."""
    return [_lf_callback] if (_enabled and _lf_callback) else []


def flush():
    if _enabled and _client:
        _client.flush()
