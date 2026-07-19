from app.client import ChatResult
from app.handlers import render_result, MSG_REJECTED, MSG_ERROR


def test_render_ok_includes_answer_sources_and_quota():
    out = render_result(ChatResult(
        kind="ok", answer="Ответ",
        sources=[{"document": "A.pdf", "page": 2}],
        remaining=8, daily_limit=10,
    ))
    assert "Ответ" in out
    assert "📎 Источники:" in out
    assert "A.pdf, стр. 2" in out
    assert "Осталось 8 из 10" in out


def test_render_rate_limited_shows_reset_time():
    out = render_result(ChatResult(
        kind="rate_limited", daily_limit=10, reset_seconds=2 * 3600 + 30 * 60,
    ))
    assert "лимит" in out.lower()
    assert "2ч 30м" in out


def test_render_rejected():
    assert render_result(ChatResult(kind="rejected")) == MSG_REJECTED


def test_render_error():
    assert render_result(ChatResult(kind="error")) == MSG_ERROR
