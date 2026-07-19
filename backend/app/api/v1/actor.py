"""Выбор идентификатора актора для rate-limit (E4) и Langfuse (A3).

Бот ходит под ОДНИМ служебным JWT, а конкретный telegram-юзер приходит в
заголовке X-Telegram-User-Id. Доверяем заголовку ТОЛЬКО когда запрос — от
служебного bot-юзера (сверка по email из настроек), иначе обычный веб-юзер
мог бы подделать чужой telegram id и сжечь его лимит.
"""


def resolve_actor_id(
    user_email: str,
    user_id: str,
    x_telegram_user_id: str | None,
    bot_email: str | None,
) -> str:
    if x_telegram_user_id and bot_email and user_email == bot_email:
        return f"tg:{x_telegram_user_id}"
    return user_id
