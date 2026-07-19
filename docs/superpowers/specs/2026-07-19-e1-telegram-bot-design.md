# E1 — Telegram-бот поверх RAG (дизайн)

**Дата:** 2026-07-19
**Задача:** E1 (линия E — демо для коллег)
**Статус:** дизайн утверждён → writing-plans

## Цель

Живой интерактив для демо: коллеги пишут вопрос боту в Telegram (каждый со своего
аккаунта, конкурентно, ~10 человек) → бот отвечает через наш RAG + источники.
`user_id` в учёте = telegram id, чтобы в Langfuse было видно «кто что спрашивал и
почём», а rate-limit (E4) считался на каждого человека отдельно.

## Ключевые решения (из брейнсторминга 2026-07-19)

1. **Проброс telegram user_id** — через заголовок `X-Telegram-User-Id` (не отдельный
   DB-юзер на каждого, не общий сервисный бакет).
2. **Библиотека/режим** — aiogram 3, long-polling (без публичного HTTPS-URL).
3. **Сервис-аутентификация бота** — служебный bot-юзер в Postgres + `login` на старте
   (переиспользуем существующий auth, ноль правок в auth-бэке).
4. **Функции (must-have)** — минимум: вопрос → ответ + источники, `/start`, typing,
   обработка 429/400/5xx. Без истории диалога и кнопок (YAGNI).
5. **Показ остатка квоты** — под каждым ответом бот пишет строку «Осталось N из 10
   сообщений на сегодня». При исчерпании (429) — «лимит обновится через Xч Yм».
   Бэкенд отдаёт остаток/лимит/секунды-до-сброса в **HTTP-заголовках** ответа
   `/api/v1/chat` (`X-RateLimit-Remaining/-Limit/-Reset`) — схема `ChatResponse` и
   веб-контракт не меняются, заголовки чисто аддитивные.

## Архитектура

Отдельный сервис `telegram-bot` в `docker-compose` — тонкий HTTP-клиент существующей
апишки. RAG-логики в боте нет.

Поток одного сообщения:

```
Telegram user → бот получает update (polling)
  → POST /api/v1/chat
       Authorization: Bearer <сервисный JWT бота>
       X-Telegram-User-Id: <telegram id>
  → (бэкенд) gateway.check("tg:<id>") → RAGEngine.query → ChatResponse
  → бот форматирует answer + источники → отправляет в чат
```

## Компоненты

### A. Правка бэкенда — `backend/app/api/v1/chat.py`

Единственная правка ядра. Эндпоинт принимает опциональный заголовок
`X-Telegram-User-Id`. Выбор идентификатора для **gateway rate-limit** и **Langfuse
`user_id`**:

- заголовок учитывается **только если** аутентифицированный юзер — служебный bot-юзер
  (сверка по `settings.TELEGRAM_BOT_USER_EMAIL`); иначе заголовок игнорируется — чтобы
  обычный веб-юзер не подделал чужой telegram id и не сжёг его лимит;
- итоговый идентификатор — `tg:<telegram_id>` (namespace, чтобы Redis-ключ лимита и
  Langfuse `user_id` не пересекались с web-UUID);
- если заголовка нет ИЛИ юзер не bot — поведение прежнее (`str(user.id)`).

Извлечение в чистую функцию (для юнит-тестов), напр.
`resolve_actor_id(user, x_telegram_user_id, bot_email) -> str`. Веб-контур не меняется.

Новая настройка в `backend/app/config.py`: `TELEGRAM_BOT_USER_EMAIL: Optional[str] = None`.

### A2. Остаток квоты в заголовках — gateway + `chat.py`

Чтобы бот (тонкий клиент без доступа к Redis) мог показать остаток:

- `RateLimiter` получает метод `hit(user_id) -> RateLimitStatus(allowed, remaining,
  limit, reset_seconds)` — тот же INCR+EXPIRE, но возвращает и остаток (`limit - count`,
  не ниже 0) и `reset_seconds` (секунд до полуночи сервера — фактический сброс, т.к.
  ключ датовый). `is_allowed` сохраняется (делегирует в `hit`) — старые тесты целы.
- `GatewayDecision` получает опциональные поля `remaining/limit/reset_seconds`
  (default `None`); `SecurityGateway.check` заполняет их из `hit`.
- `chat.py`: при `allowed` — проставляет заголовки `X-RateLimit-Remaining/-Limit/-Reset`
  в `Response`; при `429` — те же заголовки в `HTTPException(headers=...)` (`Remaining=0`).
  На инъекцию (400) квоту не показываем.

### B. Bot-юзер в Postgres

Служебный пользователь (`role=user`), учётка из env бота. Заводится сидом/скриптом
(разово; способ — на этапе плана: alembic-сид либо разовый скрипт `make bot-seed`).
Gateway применяется к нему (role=user), но лимит считается по `tg:<id>` из заголовка,
а не по id самого bot-юзера.

### C. Сервис `telegram-bot` (aiogram 3)

Каталог `bot/` в корне репозитория. Обязанности:

- **Старт:** `POST /api/v1/auth/login` (email/пароль bot-юзера из env) → access JWT в
  память. При `401` на любом запросе — перелогин и **один** повтор.
- **`/start`:** приветствие («Задайте вопрос по документам ФПСР…»).
- **Любой текст:** `sendChatAction: typing` → `POST /api/v1/chat` с `Authorization` и
  `X-Telegram-User-Id: <message.from_user.id>` → форматирование ответа.
- **Формат ответа:** `answer` + блок источников: `📎 Источники:` строками
  `<document>, стр. <page>` (page может быть `None` → без страницы; дедуп по документу+странице)
  + строка квоты `Осталось N из <limit> сообщений на сегодня` (из заголовков ответа).
- **Stateless:** `session_id`/`X-Session-Id` не прокидываем → каждый вопрос независим
  (минимум по договорённости, без памяти диалога).
- **Токен бота:** `TELEGRAM_BOT_TOKEN` из env.

### D. HTTP-клиент бота (`bot/client.py`)

Тонкая обёртка над `httpx.AsyncClient`: логин, `chat(text, telegram_user_id)`,
хранение/рефреш токена. Маппинг статусов → доменные результаты, чтобы хендлеры не
знали про HTTP. Из заголовков ответа (200 и 429) вытаскивает `remaining/limit/
reset_seconds` в `ChatResult`.

## Обработка ошибок

| Ситуация | Ответ пользователю |
|---|---|
| `429` (rate-limit E4) | «Вы исчерпали дневной лимит (N/день). Лимит обновится через Xч Yм.» (из заголовков) |
| `400` (injection guard) | Вежливый отказ: «Не могу обработать этот запрос.» |
| таймаут / `5xx` / сеть | «Сервис временно недоступен, попробуйте позже.» |
| `401` | внутренний перелог + 1 повтор; при повторном фейле → как 5xx |
| низкая confidence | приходит как обычный `answer` («не нашёл…») — спец-обработки не нужно |

## Инфраструктура

- **`docker-compose.yml`:** сервис `telegram-bot`, `depends_on: [backend]`, env
  (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_EMAIL`, `TELEGRAM_BOT_PASSWORD`, `BACKEND_URL`).
- **Зависимости бота:** отдельно от бэка (`bot/pyproject.toml` под uv либо
  `bot/requirements.txt` — решается в плане), минимум: `aiogram`, `httpx`.
- **Makefile:** `make bot-up`, `make bot-logs` (по образцу существующих таргетов).
- **Секреты:** токен и пароль bot-юзера — только в env, в git не коммитятся.

## Тестирование (TDD)

**Бэкенд (pytest):**
- unit `resolve_actor_id`:
  - (a) bot-юзер + заголовок → `tg:<id>`;
  - (b) веб-юзер + заголовок → заголовок игнорируется, `str(user.id)`;
  - (c) нет заголовка → `str(user.id)`.
- unit `RateLimiter.hit`: остаток убывает (limit-count, не ниже 0); `reset_seconds`
  положителен; fail-open при ошибке Redis.
- integration: два разных `X-Telegram-User-Id` под bot-токеном лимитятся независимо;
  превышение лимита одного tg-id → `429`, второй tg-id ещё проходит; на `200` есть
  заголовки `X-RateLimit-*`, на `429` — тоже (`Remaining=0`).

**Бот (pytest, замоканный клиент):**
- форматирование ответа + источников (в т.ч. `page=None`, дедуп, пустой список)
  + строка квоты; `format_duration(seconds)` → «Xч Yм» / «Yм»;
- маппинг статусов `429/400/5xx` → тексты сообщений (в 429 — время сброса из заголовка);
- клиент парсит `X-RateLimit-*` из ответа (200 и 429);
- рефреш-логика: `401` → перелог + один повтор.

## Границы (в этот спек НЕ входит)

- Память диалога / контекст (session_id) — сознательно опущено.
- Кнопки, feedback 👍/👎, `/help`, показ confidence — сверх минимума (потом, если нужно).
- Webhook-режим, публичный домен.
- Изменения в auth-бэке (переиспользуем существующий login).

## Затрагиваемые файлы

- `backend/app/api/v1/chat.py` — заголовок `X-Telegram-User-Id` + `resolve_actor_id`
  + проставление заголовков `X-RateLimit-*` (правка).
- `backend/app/config.py` — `TELEGRAM_BOT_USER_EMAIL` (правка).
- `backend/app/core/gateway/rate_limiter.py` — метод `hit` + `RateLimitStatus` (правка).
- `backend/app/core/gateway/decision.py` — поля `remaining/limit/reset_seconds` (правка).
- `backend/app/core/gateway/gateway.py` — `check` заполняет поля из `hit` (правка).
- `backend/tests/...` — тесты `resolve_actor_id`, `hit`, integration квоты (новое/правка).
- `bot/` — сервис aiogram: `main.py`, `client.py`, `handlers.py`, deps, тесты (новое).
- `docker-compose.yml`, `Makefile` — сервис + таргеты (правка).
