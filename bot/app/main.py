"""Точка входа бота: long-polling. Клиент кладём в workflow_data диспетчера —
aiogram внедрит его в хендлер по имени параметра `client`."""

import asyncio
import logging

from aiogram import Bot, Dispatcher

from app.client import BackendClient
from app.config import get_settings
from app.handlers import router


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()

    client = BackendClient(
        base_url=settings.BACKEND_URL,
        email=settings.TELEGRAM_BOT_EMAIL,
        password=settings.TELEGRAM_BOT_PASSWORD,
        timeout=settings.REQUEST_TIMEOUT,
    )
    bot = Bot(settings.TELEGRAM_BOT_TOKEN)
    dp = Dispatcher()
    dp["client"] = client
    dp.include_router(router)

    try:
        await dp.start_polling(bot)
    finally:
        await client.aclose()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
