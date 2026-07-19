FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV UV_PROJECT_ENVIRONMENT=/opt/venv

# Только прод-зависимости (без dev/pytest). Lock создастся при первой сборке.
COPY pyproject.toml ./
RUN uv sync --no-dev

ENV PATH="/opt/venv/bin:$PATH"

COPY . .

CMD ["python", "-m", "app.main"]
