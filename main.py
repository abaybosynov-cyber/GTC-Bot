import os
import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.enums import ChatType, ParseMode

from openai import OpenAI

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
    "Не ставь диагнозы и не обещай гарантированный результат. "
    "Если вопрос медицинский — рекомендуй обратиться к специалисту."
)

# -----------------------------
# Bot / Dispatcher
# -----------------------------
bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

logging.basicConfig(level=logging.INFO)


def topic_id_of(message: Message):
    # В темах Telegram forum это message_thread_id (int)
    return message.message_thread_id


# 1) ГЛОБАЛЬНЫЙ ФИЛЬТР: удаляет ВСЁ вне тем 1/7 (любой тип контента)
@dp.message(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
async def enforce_topics(message: Message):
    # Не трогаем сообщения самого бота
    if message.from_user and message.from_user.is_bot:
        return

    tid = topic_id_of(message)

    # Лог для контроля (посмотри в консоли/Railway logs)
    logging.info(f"IN: chat={message.chat.id} tid={tid} msg={message.message_id} text={bool(message.text)}")

    # Если не из разрешённой темы — удалить и остановиться
    if tid not in ALLOWED_TOPICS:
        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
        except Exception as e:
            logging.error(f"DELETE FAILED: chat={message.chat.id} msg={message.message_id} err={e}")
        return

    # Если тема разрешена — пропускаем дальше (не отвечаем тут)
    # Важно: дальше будет отдельный handler на ответ AI


# 2) ОТВЕТ AI: только текст и только в темах 1/7
@dp.message(
    F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}) &
    F.text
)
async def ai_reply(message: Message):
    tid = topic_id_of(message)
    if tid not in ALLOWED_TOPICS:
        return

    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.2,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": message.text},
            ],
        )
        answer = completion.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"OPENAI FAILED: err={e}")
        await message.reply("Сервис временно недоступен. Попробуйте позже.")
        return

    if len(answer) > 3500:
        answer = answer[:3500] + "…"

    await message.reply(answer)


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

