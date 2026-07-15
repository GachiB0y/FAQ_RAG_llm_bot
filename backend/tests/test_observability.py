import math

from app.core import observability as obs


def setup_function():
    # каждый тест стартует с чистого выключенного состояния
    obs._client = None
    obs._enabled = False
    obs._lf_callback = None


def test_prompt_hash_deterministic_and_short():
    h1 = obs.prompt_hash("hello prompt")
    h2 = obs.prompt_hash("hello prompt")
    assert h1 == h2
    assert len(h1) == 8
    assert obs.prompt_hash("other") != h1


def test_init_disabled_returns_false():
    assert obs.init_observability(False, None, None, None) is False
    assert obs._enabled is False
    assert obs._client is None


def test_trace_context_disabled_is_noop():
    with obs.trace_context(user_id="u1", session_id="s1", tags=["dense"]) as h:
        assert h.id is None
        h.update(metadata={"confidence": 0.9})  # не должно падать


def test_push_scores_disabled_noop():
    obs.push_scores(None, {"faithfulness": 0.8})  # не должно падать/слать сеть


def test_langchain_callbacks_disabled_empty():
    assert obs.langchain_callbacks() == []


def test_flush_disabled_noop():
    obs.flush()  # не должно падать


def test_push_scores_enabled_maps_and_skips_nan():
    calls = []

    class FakeClient:
        def create_score(self, *, trace_id, name, value):
            calls.append((trace_id, name, value))

    obs._enabled = True
    obs._client = FakeClient()
    obs.push_scores(
        "trace-123",
        {"faithfulness": 0.9, "answer_relevancy": math.nan, "recall": None},
    )

    assert ("trace-123", "faithfulness", 0.9) in calls
    assert all(name != "answer_relevancy" for _, name, _ in calls)  # NaN пропущен
    assert all(name != "recall" for _, name, _ in calls)            # None пропущен


def test_trace_context_enabled_stamps_identity_and_captures_id():
    span_names = []
    trace_updates = []

    class FakeSpanCtx:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class FakeClient:
        def start_as_current_span(self, *, name):
            span_names.append(name)
            return FakeSpanCtx()

        def update_current_trace(self, **kwargs):
            trace_updates.append(kwargs)

        def get_current_trace_id(self):
            return "trace-xyz"

    obs._enabled = True
    obs._client = FakeClient()

    with obs.trace_context(
        user_id="eval:x:1", session_id="run-1", tags=["dense"], metadata={"top_k": 5}
    ) as h:
        assert h.id == "trace-xyz"
        h.update(metadata={"chunks": 3})

    assert span_names == ["rag-query"]
    # первый вызов — идентичность трейса
    first = trace_updates[0]
    assert first["user_id"] == "eval:x:1"
    assert first["session_id"] == "run-1"
    assert first["tags"] == ["dense"]
    assert first["metadata"] == {"top_k": 5}
    # второй вызов — h.update(metadata=...)
    assert trace_updates[1]["metadata"] == {"chunks": 3}
