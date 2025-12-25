import os
import json
import time
import urllib.parse
import urllib.request

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not BOT_TOKEN:
    raise RuntimeError("Missing BOT_TOKEN")
if not OPENAI_API_KEY:
    raise RuntimeError("Missing OPENAI_API_KEY")

ALLOWED_TOPICS = {1, 7}  # разрешённые темы

SYSTEM_PROMPT = (
    "Ты FAQ-ассистент компании Global Trend. "
    "Отвечай кратко и по делу. "
    "Не ставь диагнозы, не обещай гарантированный результат. "
    "Если вопрос медицинский — рекомендуй обратиться к специалисту."
)

TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

def tg(method: str, payload: dict):
    url = f"{TG_API}/{method}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))

def openai_chat(user_text: str) -> str:
    url = "https://api.openai.com/v1/chat/completions"
    payload = {
        "model": "gpt-4o-mini",
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text}
        ]
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OPENAI_API_KEY}",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        out = json.loads(resp.read().decode("utf-8"))
    return out["choices"][0]["message"]["content"].strip()

def main():
    offset = None
    print("Bot started (no external libs).")

    while True:
        try:
            params = {"timeout": 25}
            if offset is not None:
                params["offset"] = offset

            # getUpdates with long polling
            updates = tg("getUpdates", params)
            if not updates.get("ok"):
                time.sleep(2)
                continue

            for upd in updates.get("result", []):
                offset = upd["update_id"] + 1

                msg = upd.get("message")
                if not msg:
                    continue

                chat = msg.get("chat", {})
                chat_id = chat.get("id")
                message_id = msg.get("message_id")
                text = msg.get("text")
                topic_id = msg.get("message_thread_id")  # форумная тема

                # если не в разрешённой теме — удалить и не отвечать
                if topic_id not in ALLOWED_TOPICS:
                    try:
                        tg("deleteMessage", {"chat_id": chat_id, "message_id": message_id})
                    except Exception:
                        pass
                    continue

                # отвечаем только на текст
                if not text:
                    continue

                try:
                    answer = openai_chat(text)
                except Exception:
                    answer = "Сервис временно недоступен. Попробуйте позже."

                if len(answer) > 3500:
                    answer = answer[:3500] + "…"

                tg("sendMessage", {
                    "chat_id": chat_id,
                    "message_thread_id": topic_id,  # ответ именно в этой теме
                    "reply_to_message_id": message_id,
                    "text": answer
                })

        except Exception as e:
            # чтобы бот не умирал из-за временных сетевых ошибок
            print("Loop error:", e)
            time.sleep(2)

if __name__ == "__main__":
    main()

