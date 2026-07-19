from app.formatting import dedup_sources, format_duration, format_reply


def test_format_reply_answer_only():
    assert format_reply("Ответ.", []) == "Ответ."


def test_format_reply_with_sources():
    out = format_reply("Ответ.", [{"document": "Устав.pdf", "page": 3, "chunk": "..."}])
    assert out == "Ответ.\n\n📎 Источники:\n• Устав.pdf, стр. 3"


def test_format_reply_source_without_page():
    out = format_reply("Ответ.", [{"document": "FAQ.md", "page": None, "chunk": "x"}])
    assert out == "Ответ.\n\n📎 Источники:\n• FAQ.md"


def test_format_reply_appends_quota_line():
    out = format_reply("Ответ.", [], remaining=9, limit=10)
    assert out == "Ответ.\n\nОсталось 9 из 10 сообщений на сегодня."


def test_format_reply_sources_and_quota():
    out = format_reply(
        "Ответ.", [{"document": "A.pdf", "page": 1}], remaining=4, limit=10
    )
    assert out == (
        "Ответ.\n\n📎 Источники:\n• A.pdf, стр. 1"
        "\n\nОсталось 4 из 10 сообщений на сегодня."
    )


def test_dedup_sources_by_document_and_page():
    src = [
        {"document": "A.pdf", "page": 1},
        {"document": "A.pdf", "page": 1},
        {"document": "A.pdf", "page": 2},
    ]
    assert dedup_sources(src) == [
        {"document": "A.pdf", "page": 1},
        {"document": "A.pdf", "page": 2},
    ]


def test_format_duration_hours_and_minutes():
    assert format_duration(3 * 3600 + 12 * 60) == "3ч 12м"


def test_format_duration_minutes_only():
    assert format_duration(45 * 60) == "45м"
