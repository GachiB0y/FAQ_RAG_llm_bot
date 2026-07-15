# FAQ RAG Bot — команды-ярлыки.
# Запуск: make <цель>. Список: make help.
#
# Модели можно переопределять: make eval-dense JUDGE_MODEL=openai/gpt-5.4

BACKEND      := faq_rag_llm_bot-backend-1
CORPUS       := /tmp/corpus
# ключ OpenRouter берём из .env.eval (в git не коммитится)
OPENROUTER_KEY := $(shell grep '^OPENROUTER_API_KEY=' .env.eval 2>/dev/null | cut -d= -f2-)

# Langfuse (A3): ключи из .env.eval, флаг выключен по умолчанию.
# Включить прогон с трейсами: make eval-dense LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC := $(shell grep '^LANGFUSE_PUBLIC_KEY=' .env.eval 2>/dev/null | cut -d= -f2-)
LANGFUSE_SECRET := $(shell grep '^LANGFUSE_SECRET_KEY=' .env.eval 2>/dev/null | cut -d= -f2-)
LANGFUSE_HOST ?= http://host.docker.internal:3001
LANGFUSE_ENABLED ?= false
GIT_COMMIT := $(shell git rev-parse --short HEAD 2>/dev/null)

# модели пула — единственный источник в backend/models.env (см. комментарии там).
# ~$0.4-1.5 за цикл eval (судья = ~95% стоимости). Обоснование — docs/plans/2026-07-08-model-flow.md
# Переопределение на прогон: make eval-dense GEN_MODEL=... (CLI старше include).
include backend/models.env
TESTSET_SIZE ?= 15
MAX_CHUNKS   ?= 80

# общий набор env для eval-прогонов (не дублируем в каждой цели).
# Имена env — ролевые: JUDGE и KG больше не делят одну переменную OPENROUTER_MODEL.
EVAL_ENV = -e OPENROUTER_API_KEY="$(OPENROUTER_KEY)" -e DATASET_SOURCE=json \
	-e GENERATOR_PROVIDER=openrouter -e OPENROUTER_GEN_MODEL="$(GEN_MODEL)" \
	-e JUDGE_PROVIDER=openrouter -e OPENROUTER_JUDGE_MODEL="$(JUDGE_MODEL)" \
	-e LANGFUSE_ENABLED="$(LANGFUSE_ENABLED)" \
	-e LANGFUSE_PUBLIC_KEY="$(LANGFUSE_PUBLIC)" \
	-e LANGFUSE_SECRET_KEY="$(LANGFUSE_SECRET)" \
	-e LANGFUSE_HOST="$(LANGFUSE_HOST)" \
	-e LANGFUSE_TRACING_ENVIRONMENT=eval \
	-e GIT_COMMIT="$(GIT_COMMIT)"

.PHONY: help up down rebuild logs shell corpus ingest ingest-hybrid ocr kg testset \
	eval-dense eval-hybrid mlflow-ui mlflow-stop langfuse-up langfuse-down langfuse-prices

help: ## Показать все команды
	@grep -E '^[a-z-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

# ─────────────── инфраструктура ───────────────
up: ## Поднять весь docker-стек
	docker compose up -d

down: ## Погасить стек
	docker compose down

rebuild: ## Пересобрать backend-образ (после правок зависимостей)
	docker compose build backend

logs: ## Логи backend (follow)
	docker logs -f $(BACKEND)

shell: ## Bash внутри backend-контейнера
	docker exec -it $(BACKEND) bash

# ─────────────── данные ───────────────
corpus: ## Скопировать тестовые документы в контейнер (/tmp/corpus)
	docker exec $(BACKEND) mkdir -p $(CORPUS)
	docker cp docs_for_test_rag/. $(BACKEND):$(CORPUS)/
	@echo "Скопировано в $(CORPUS). Битый PDF-картинку не забудь OCR-ить: make ocr"

ingest: ## Загрузить корпус в dense-коллекцию (documents)
	docker exec $(BACKEND) python -u scripts/ingest_local.py $(CORPUS)

ingest-hybrid: ## Загрузить корпус в hybrid-коллекцию (documents_hybrid)
	docker exec $(BACKEND) python -u scripts/ingest_hybrid.py

ocr: ## OCR картинок-PDF через Tesseract (rus)
	docker exec -e OCR_PROVIDER=tesseract -e OCR_DPI=300 $(BACKEND) \
	  python -u scripts/ocr_image_pdf.py

# ─────────────── Ragas pipeline ───────────────
kg: ## Построить knowledge graph (OpenRouter)
	docker exec -e OPENROUTER_API_KEY="$(OPENROUTER_KEY)" -e MAX_CHUNKS_PER_DOC=$(MAX_CHUNKS) \
	  -e OPENROUTER_KG_MODEL="$(KG_MODEL)" $(BACKEND) python -u scripts/generate_kg.py

testset: ## Сгенерировать testset (OpenRouter)
	docker exec -e OPENROUTER_API_KEY="$(OPENROUTER_KEY)" -e TESTSET_SIZE=$(TESTSET_SIZE) \
	  -e OPENROUTER_KG_MODEL="$(KG_MODEL)" $(BACKEND) python -u scripts/generate_testset.py

eval-dense: ## Прогон Ragas eval — dense retrieval
	docker exec $(EVAL_ENV) $(BACKEND) python -u scripts/eval_rag.py

eval-hybrid: ## Прогон Ragas eval — hybrid retrieval
	docker exec $(EVAL_ENV) -e HYBRID=true $(BACKEND) python -u scripts/eval_rag.py

# ─────────────── UI ───────────────
mlflow-ui: ## Поднять MLflow UI на localhost:5050
	docker run --rm -d --name mlflow-ui -p 5050:5050 -v $(CURDIR)/backend:/app \
	  python:3.11-slim \
	  sh -c "pip install --quiet mlflow && mlflow ui --backend-store-uri sqlite:////app/mlflow.db --host 0.0.0.0 --port 5050"
	@echo "MLflow UI: http://localhost:5050"

mlflow-stop: ## Остановить MLflow UI
	docker stop mlflow-ui

# ─────────────── Langfuse (A3) ───────────────
langfuse-up: ## Поднять Langfuse (UI на localhost:3001)
	docker compose -f docker-compose.langfuse.yml up -d
	@echo ">> Langfuse UI: http://localhost:3001 (создай проект → ключи в .env.eval)"

langfuse-down: ## Остановить Langfuse
	docker compose -f docker-compose.langfuse.yml down

langfuse-prices: ## Задать custom model prices в Langfuse (A3.2, идемпотентно)
	docker exec \
	  -e LANGFUSE_HOST="$(LANGFUSE_HOST)" \
	  -e LANGFUSE_PUBLIC_KEY="$(LANGFUSE_PUBLIC)" \
	  -e LANGFUSE_SECRET_KEY="$(LANGFUSE_SECRET)" \
	  -e GEN_MODEL="$(GEN_MODEL)" -e JUDGE_MODEL="$(JUDGE_MODEL)" -e KG_MODEL="$(KG_MODEL)" \
	  $(BACKEND) python -u scripts/langfuse_set_prices.py
