"""aiogram-роутер бота: /start и обработка вопросов. RAG-логики нет —
всё уходит в BackendClient, ответ маппится в текст render_result."""

from aiogram import Router
from aiogram.enums import ChatAction
from aiogram.filters import CommandStart
from aiogram.types import Message

from app.client import BackendClient, ChatResult
from app.formatting import format_duration, format_reply

router = Router()

WELCOME = (
    "Здравствуйте! Я отвечаю на вопросы по документам ФПСР. "
    "Просто напишите вопрос."
)
MSG_REJECTED = "Извините, я не могу обработать этот запрос."
MSG_ERROR = "Сервис временно недоступен, попробуйте позже."


def render_result(result: ChatResult) -> str:
    if result.kind == "ok":
        return format_reply(
            result.answer, result.sources, result.remaining, result.daily_limit
        )
    if result.kind == "rate_limited":
        limit = result.daily_limit if result.daily_limit is not None else "?"
        reset = (
            format_duration(result.reset_seconds)
            if result.reset_seconds is not None
            else "завтра"
        )
        return f"Вы исчерпали дневной лимит ({limit}/день). Лимит обновится через {reset}."
    if result.kind == "rejected":
        return MSG_REJECTED
    return MSG_ERROR


@router.message(CommandStart())
async def on_start(message: Message) -> None:
    await message.answer(WELCOME)


@router.message()
async def on_question(message: Message, client: BackendClient) -> None:
    if not message.text:
        return
    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    result = await client.chat(message.text, message.from_user.id)
    await message.answer(render_result(result))
