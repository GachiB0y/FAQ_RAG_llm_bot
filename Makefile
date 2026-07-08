# FAQ RAG Bot — команды-ярлыки.
# Запуск: make <цель>. Список: make help.
#
# Модели можно переопределять: make eval-dense JUDGE_MODEL=google/gemma-4-31b-it:free

BACKEND      := faq_rag_llm_bot-backend-1
CORPUS       := /tmp/corpus
# ключ OpenRouter берём из .env.eval (в git не коммитится)
OPENROUTER_KEY := $(shell grep '^OPENROUTER_API_KEY=' .env.eval 2>/dev/null | cut -d= -f2-)

# модели по умолчанию (переопределяемы через make VAR=...)
GEN_MODEL    ?= nvidia/nemotron-3-super-120b-a12b:free
JUDGE_MODEL  ?= openai/gpt-oss-120b:free
KG_MODEL     ?= google/gemma-4-31b-it:free
TESTSET_SIZE ?= 15
MAX_CHUNKS   ?= 80

# общий набор env для eval-прогонов (не дублируем в каждой цели)
EVAL_ENV = -e OPENROUTER_API_KEY="$(OPENROUTER_KEY)" -e DATASET_SOURCE=json \
	-e GENERATOR_PROVIDER=openrouter -e OPENROUTER_GEN_MODEL="$(GEN_MODEL)" \
	-e JUDGE_PROVIDER=openrouter -e OPENROUTER_MODEL="$(JUDGE_MODEL)"

.PHONY: help up down rebuild logs shell corpus ingest ingest-hybrid ocr kg testset \
	eval-dense eval-hybrid mlflow-ui mlflow-stop

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
	  -e OPENROUTER_MODEL="$(KG_MODEL)" $(BACKEND) python -u scripts/generate_kg.py

testset: ## Сгенерировать testset (OpenRouter)
	docker exec -e OPENROUTER_API_KEY="$(OPENROUTER_KEY)" -e TESTSET_SIZE=$(TESTSET_SIZE) \
	  -e OPENROUTER_MODEL="$(KG_MODEL)" $(BACKEND) python -u scripts/generate_testset.py

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
