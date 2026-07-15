#!/usr/bin/env python3
"""Задать custom model prices в Langfuse для наших OpenRouter-слагов (задача A3.2).

Зачем: Langfuse считает $/запрос, только если знает цену модели. Наши имена
(`qwen/…`, `openai/…`, `google/…`) в справочнике Langfuse отсутствуют → без этого
cost = $0 (токены есть, умножать не на что).

Запуск (через Makefile, env приходят оттуда): make langfuse-prices

Идемпотентно: создаёт модель, только если имени ещё нет. Повторный запуск —
no-op (Langfuse резервирует имя модели навсегда через soft-delete, пересоздать
по имени нельзя). **Сменить цену уже созданной модели** — в UI (Settings → Models)
или пересоздать Langfuse с чистого тома (`make langfuse-down` + `docker volume rm`);
цены у нас стабильны (model-flow), так что create-once достаточно.

Имена моделей — из backend/models.env (единый источник, приходят через env).
Цены — из docs/plans/2026-07-08-model-flow.md, $/1M токенов (in/out).
"""
import os
import sys

import httpx

HOST = os.environ.get("LANGFUSE_HOST", "http://localhost:3001")
PUBLIC_KEY = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
SECRET_KEY = os.environ.get("LANGFUSE_SECRET_KEY", "")

# Цены $/1M токенов (input, output). Источник — model-flow.md.
# Ключ — слаг OpenRouter (как он придёт в трейс из models.env). Нет слага в таблице
# → скрипт предупредит и пропустит (значит: добавь цену сюда при добавлении модели).
PRICES_PER_1M = {
    "qwen/qwen3.6": (0.32, 1.28),
    "openai/gpt-5.4": (2.50, 15.00),
    "google/gemini-3.1-flash-lite": (0.25, 1.50),
    # известные альтернативы из model-flow (на случай смены в models.env):
    "google/gemini-3.1-flash": (0.30, 2.50),
    "deepseek/deepseek-v4-flash": (0.14, 0.28),
}

# Какие роли забираем из env (Makefile прокидывает из models.env).
ROLE_ENVS = ["GEN_MODEL", "JUDGE_MODEL", "KG_MODEL"]


def slug_to_regex(slug: str) -> str:
    """Точное совпадение имени модели (спецсимволы экранированы), регистронезависимо."""
    escaped = slug.replace(".", r"\.").replace("/", r"\/")
    return f"(?i)^{escaped}$"


def main() -> None:
    if not PUBLIC_KEY or not SECRET_KEY:
        sys.exit("LANGFUSE_PUBLIC_KEY/SECRET_KEY не заданы — заполни .env.eval (см. make langfuse-up)")

    auth = (PUBLIC_KEY, SECRET_KEY)
    base = HOST.rstrip("/")

    # Уникальные слаги из ролей (одна модель может быть в нескольких ролях).
    slugs = []
    for env_name in ROLE_ENVS:
        slug = os.environ.get(env_name, "").strip()
        if slug and slug not in slugs:
            slugs.append(slug)

    if not slugs:
        sys.exit("Ни один из GEN_MODEL/JUDGE_MODEL/KG_MODEL не задан — запускай через make")

    with httpx.Client(auth=auth, timeout=30) as client:
        # Идемпотентность через сам POST: имя уникально в проекте, повторный POST →
        # "already exists" → считаем заданным. (Пре-GET не делаем: список моделей
        # пагинирован — Langfuse засеян сотнями managed-моделей, наши могут быть за
        # первой страницей, и фильтра по имени в API нет.)
        for slug in slugs:
            if slug not in PRICES_PER_1M:
                print(f"  [!] {slug}: нет цены в PRICES_PER_1M — пропуск (добавь цену в скрипт)")
                continue

            in_1m, out_1m = PRICES_PER_1M[slug]
            body = {
                "modelName": slug,
                "matchPattern": slug_to_regex(slug),
                "unit": "TOKENS",
                "inputPrice": in_1m / 1_000_000,
                "outputPrice": out_1m / 1_000_000,
            }
            r = client.post(f"{base}/api/public/models", json=body)
            if r.status_code >= 400:
                if "already exists" in r.text:
                    print(f"  [skip] {slug}: уже задана (смена цены — в UI)")
                else:
                    print(f"  [FAIL] {slug}: {r.status_code} {r.text[:200]}")
                continue
            print(f"  [OK] {slug}: in ${in_1m}/1M, out ${out_1m}/1M")

    print(">> Цены заданы. Проверка: Langfuse UI → Settings → Models.")


if __name__ == "__main__":
    main()
