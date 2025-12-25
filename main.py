import os
import asyncio
import logging
from typing import Optional

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.enums import ParseMode

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# -----------------------------
# Config
# -----------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not BOT_TOKEN:
    raise RuntimeError("Missing BOT_TOKEN env var")
if not OPENAI_API_KEY:
    raise RuntimeError("Missing OPENAI_API_KEY env var")

client = OpenAI(api_key=OPENAI_API_KEY)

ALLOWED_TOPICS = {1, 7}  # Дискуссия, Вопрос–Ответ

SYSTEM_PROMPT = (
    "Ты FAQ-ассистент компании Global Trend. "
    "Отвечай кратко и по делу. "
    "Не ставь диагнозы, не обещай гарантированный результат, "
    "не давай медицинских назначений. "
    "Если вопрос медицинский — рекомендуй обратиться к специалисту."
)

# -----------------------------
# Bot / Dispatcher
# -----------------------------
bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()


def get_topic_id(message: Message) -> Optional[int]:
    """
    For forum topics in Telegram groups, aiogram v3 exposes message_thread_id.
    If message is not from a topic, it may be None.
    """
    return message.message_thread_id


async def ask_openai(user_text: str) -> str:
    """
    Calls OpenAI Chat Completions (OpenAI Python SDK v1+).
    """
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        temperature=0.2,
    )
    return completion.choices[0].message.content.strip()


@dp.message(F.text)
async def on_text(message: Message) -> None:
    topic_id = get_topic_id(message)

    # If you want to allow DMs too, handle message.chat.type == "private" separately.
    # Here we focus on group topics restriction logic.
    if topic_id is None or topic_id not in ALLOWED_TOPICS:
        # Delete messages outside allowed topics
        try:
            await message.delete()
        except Exception:
            # no rights or message already deleted
            pass
        return

    # Allowed topics: answer with AI
    try:
        answer = await ask_openai(message.text)
    except Exception:
        # Safe fallback if OpenAI call fails
        await message.reply("Сервис временно недоступен. Попробуйте позже.")
        return

    # Prevent super-long messages
    if len(answer) > 3500:
        answer = answer[:3500] + "…"

    await message.reply(answer)


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
