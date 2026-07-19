# Makefile — вводная (что, как, зачем нам) перед реализацией

**Дата:** 2026-07-06
**Зачем:** понять инструмент ДО кода. Что такое Makefile, как работает, как настроим
под проект, с примерами. Это Шаг B из MLOps-плана (лечит боль #1 «ручной труд»).

---

## 1. Что это в одном предложении

**Makefile — это список именованных команд-ярлыков.** Вместо того чтобы помнить и
копипастить длинную команду, пишешь `make eval` — и Makefile выполняет заранее
записанную за этим именем простыню.

Аналогия: это «горячие клавиши» для терминала. `make eval` = «нажми на кнопку
которая делает вот эти 5 строк».

---

## 2. Зачем он НАМ конкретно

Вспомни как мы запускали eval:
```bash
OPENROUTER_KEY=$(grep '^OPENROUTER_API_KEY=' .env.eval | cut -d= -f2-)
docker exec -e OPENROUTER_API_KEY="$OPENROUTER_KEY" -e DATASET_SOURCE=json \
  -e GENERATOR_PROVIDER=openrouter -e OPENROUTER_GEN_MODEL="nvidia/nemotron..." \
  -e JUDGE_PROVIDER=openrouter -e OPENROUTER_MODEL="openai/gpt-oss-120b:free" \
  faq_rag_llm_bot-backend-1 python -u scripts/eval_rag.py
```

Это **простыня, которую я копипастил каждый раз** и легко ошибиться. Плюс их было
много (ingest, kg, testset, dense-eval, hybrid-eval, mlflow-ui...).

| Наша боль | Как Makefile лечит |
|---|---|
| Копипаст длинных `docker exec -e ...` | `make eval-dense` |
| Легко забыть флаг/опечататься | команда записана один раз, правильно |
| Ключ из .env.eval подставлять руками | Makefile сам его подхватывает |
| Новый человек не знает как запускать | `make help` покажет все команды |

---

## 3. Как устроено (модель Makefile)

Файл называется `Makefile` (без расширения), лежит в корне. Состоит из **целей**
(targets):

```makefile
имя-цели:
	команда1        # ← ОБЯЗАТЕЛЬНО таб, не пробелы!
	команда2
```

Запуск: `make имя-цели`.

⚠️ **Главная ловушка Makefile:** отступ — это **таб**, не пробелы. Пробелы →
ошибка `missing separator`. Единственная реальная засада для новичка.

---

## 4. Минимальный пример (наш случай)

```makefile
# переменные — вычисляются один раз
OPENROUTER_KEY := $(shell grep '^OPENROUTER_API_KEY=' .env.eval | cut -d= -f2-)
BACKEND := faq_rag_llm_bot-backend-1

# поднять/погасить стек
up:
	docker compose up -d

down:
	docker compose down

# загрузка корпуса
ingest:
	docker exec $(BACKEND) python scripts/ingest_local.py /tmp/corpus

# eval — dense (простыня спрятана сюда)
eval-dense:
	docker exec -e OPENROUTER_API_KEY="$(OPENROUTER_KEY)" \
	  -e DATASET_SOURCE=json -e GENERATOR_PROVIDER=openrouter \
	  -e JUDGE_PROVIDER=openrouter -e OPENROUTER_MODEL="openai/gpt-oss-120b:free" \
	  $(BACKEND) python -u scripts/eval_rag.py

# eval — hybrid (то же + HYBRID=true)
eval-hybrid:
	docker exec -e OPENROUTER_API_KEY="$(OPENROUTER_KEY)" \
	  -e DATASET_SOURCE=json -e HYBRID=true -e GENERATOR_PROVIDER=openrouter \
	  -e JUDGE_PROVIDER=openrouter -e OPENROUTER_MODEL="openai/gpt-oss-120b:free" \
	  $(BACKEND) python -u scripts/eval_rag.py
```

Теперь вместо простыни:
```bash
make up
make ingest
make eval-dense
make eval-hybrid
```

---

## 5. Как мы хотим настроить (полный набор целей под проект)

| Команда | Что делает |
|---|---|
| `make up` / `make down` | поднять / погасить docker-стек |
| `make ingest` | загрузка корпуса в dense-коллекцию |
| `make ingest-hybrid` | загрузка в hybrid-коллекцию |
| `make ocr` | OCR картинок-PDF (Tesseract) |
| `make kg` | построить knowledge graph |
| `make testset` | сгенерировать testset |
| `make eval-dense` | прогон eval (dense) |
| `make eval-hybrid` | прогон eval (hybrid) |
| `make mlflow-ui` | поднять MLflow UI (sidecar) |
| `make jupyter` | поднять Jupyter Lab |
| `make help` | список всех команд с описанием |

### `make help` — приятная мелочь
```makefile
help:
	@grep -E '^[a-z-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'
```
Тогда пишешь описания через `## ...`:
```makefile
eval-dense: ## Прогон Ragas eval на dense retrieval
	...
```
И `make help` красиво их выводит. Самодокументируемо.

---

## 6. Что вынесем на реализации

1. Создать `Makefile` в корне
2. Перенести все наши `docker exec ...` простыни в цели
3. Подхват ключа из `.env.eval` через переменную
4. `make help` для самодокументации
5. Проверить: `make eval-dense` работает как раньше, но одной командой

**Готово когда:** весь пайплайн запускается через `make <target>`, простыни
`docker exec -e ...` больше не копипастим.

---

## 7. Makefile vs uv vs Prefect (не путать роли)

| Инструмент | Отвечает на вопрос |
|---|---|
| **uv** (Шаг A) | «какие версии пакетов поставить» (окружение) |
| **Makefile** (Шаг B) | «как запустить одной командой» (ярлыки) |
| **Prefect** (Шаг F) | «как запустить с retry + по расписанию + UI» (оркестрация) |

Порядок неслучаен: сначала окружение (uv), потом ярлыки (Makefile), потом — если
надо — оркестрация поверх (Prefect). Makefile — самый простой, но закрывает 80%
боли «ручной труд» сразу.

---

## 8. Чего НЕ делаем

- Не пишем сложную логику в Makefile (условия, циклы) — для этого есть Python/Prefect
- Makefile = только ярлыки на команды, не место для бизнес-логики
- Не дублируем то что уже в скриптах — Makefile их вызывает, не переписывает
