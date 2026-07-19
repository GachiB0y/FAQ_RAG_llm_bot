FROM python:3.11-slim

# uv — берём готовый бинарь из официального образа (быстро, без pip)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Системные пакеты: сборка + сеть + OCR (tesseract с русским, poppler).
# OCR раньше ставили руками в контейнер — теперь запечён в образ.
RUN apt-get update && apt-get install -y \
    build-essential \
    netcat-openbsd \
    curl \
    tesseract-ocr \
    tesseract-ocr-rus \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# venv кладём в /opt/venv, НЕ в /app/.venv — иначе bind-mount ./backend:/app
# из docker-compose перекроет его хостовой папкой (где venv нет) и всё сломается.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv

# Ставим зависимости из lock (воспроизводимо). --frozen = не менять lock.
# --group eval включает eval-зависимости (ragas/mlflow/...), т.к. eval-скрипты
# сейчас гоняются в этом же контейнере. Для чистого прод-образа убрать --group eval.
# --no-install-project — ставим только зависимости, сам проект запускаем из исходников.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --group eval --no-install-project

# venv в PATH → alembic/uvicorn/python берутся из него (и mount /app его не трогает)
ENV PATH="/opt/venv/bin:$PATH"

COPY . .

RUN chmod +x scripts/entrypoint.sh

CMD ["./scripts/entrypoint.sh"]
