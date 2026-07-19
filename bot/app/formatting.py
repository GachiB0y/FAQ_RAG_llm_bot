"""Форматирование ответа RAG для Telegram (простой текст, без разметки)."""


def dedup_sources(sources: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for s in sources:
        key = (s.get("document"), s.get("page"))
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


def format_duration(seconds: int) -> str:
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    if hours:
        return f"{hours}ч {minutes}м"
    return f"{minutes}м"


def format_reply(
    answer: str,
    sources: list[dict],
    remaining: int | None = None,
    limit: int | None = None,
) -> str:
    parts = [answer]

    unique = dedup_sources(sources)
    if unique:
        lines = ["📎 Источники:"]
        for s in unique:
            doc = s.get("document", "документ")
            page = s.get("page")
            lines.append(f"• {doc}, стр. {page}" if page is not None else f"• {doc}")
        parts.append("\n".join(lines))

    if remaining is not None and limit is not None:
        parts.append(f"Осталось {remaining} из {limit} сообщений на сегодня.")

    return "\n\n".join(parts)
