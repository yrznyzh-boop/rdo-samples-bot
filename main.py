import json
import logging
import os
from pathlib import Path
from typing import Any

from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
)
log = logging.getLogger("rdo_bot")
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
DATA_FILE = Path(os.getenv("DATA_FILE", "data.json"))

# Optional Telegram sticker file_ids. Leave empty to use the text alternatives.
STICKERS = {
    key: os.getenv(f"STICKER_{key.upper()}", "").strip()
    for key in ("start", "request", "turn", "stop", "list")
}


def load_db() -> dict[str, Any]:
    if not DATA_FILE.exists():
        return {"chats": {}}
    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("chats"), dict):
            return data
    except (OSError, json.JSONDecodeError):
        log.exception("Could not read %s; starting with empty data", DATA_FILE)
    return {"chats": {}}


db = load_db()


def save_db() -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp = DATA_FILE.with_suffix(DATA_FILE.suffix + ".tmp")
    temp.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(DATA_FILE)


def chat_data(chat_id: int) -> dict[str, Any]:
    return db["chats"].setdefault(str(chat_id), {"distributions": {}})


def display_name(user) -> str:
    return f"@{user.username}" if user.username else (user.full_name or str(user.id))


async def say(message, key: str, text: str) -> None:
    sticker_id = STICKERS.get(key, "")
    if sticker_id:
        try:
            await message.reply_sticker(sticker_id)
            return
        except Exception:
            log.exception("Sticker %s could not be sent; using text", key)
    await message.reply_text(text)


def get_distribution(chat_id: int, target_message_id: int):
    return chat_data(chat_id)["distributions"].get(str(target_message_id))


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    if not message or not user or user.is_bot or not chat:
        return

    text = (message.text or message.caption or "").strip()
    if not text:
        return
    reply = message.reply_to_message
    chat_state = chat_data(chat.id)

    # Start a distinct distribution by replying to the owner's own original post.
    if text == "توزيع":
        if not reply or not reply.from_user or reply.from_user.id != user.id:
            await message.reply_text("ابدأ التوزيع بالرد على رسالتك الأصلية في القروب بكلمة: توزيع")
            return
        key = str(reply.message_id)
        chat_state["distributions"][key] = {
            "owner_id": user.id,
            "owner_name": display_name(user),
            "active": True,
            "requests": [],
        }
        save_db()
        await say(message, "start", "💞 تم بدء التوزيع! اكتب آيديك كرد على الرسالة الأصلية.")
        return

    # Commands must be replies to the specific original post, so parallel distributions stay separate.
    if text in ("قائمة", "وقف توزيع"):
        dist = None
        if reply:
            dist = get_distribution(chat.id, reply.message_id)
        if not dist:
            await message.reply_text("رد على الرسالة الأصلية الخاصة بتوزيعك ثم اكتب قائمة أو وقف توزيع.")
            return
        if dist["owner_id"] != user.id:
            await message.reply_text("هذا الأمر متاح لصاحب التوزيع فقط.")
            return

        requests = dist["requests"]
        if text == "قائمة":
            if not requests:
                await message.reply_text("📋 لا توجد طلبات حتى الآن.")
                return
            lines = ["📋 قائمة الطلبات:"]
            lines.extend(f"{i}. {item['name']} — {item['game_id']}" for i, item in enumerate(requests, 1))
            # Telegram message limit is 4096 characters; split safely.
            chunk = ""
            for line in lines:
                if len(chunk) + len(line) + 1 > 3800:
                    await message.reply_text(chunk)
                    chunk = ""
                chunk += line + "\n"
            if chunk:
                await message.reply_text(chunk.rstrip())
            return

        dist["active"] = False
        save_db()
        lines = ["🎉 انتهى التوزيع!", f"عدد المشاركين: {len(requests)}"]
        lines.extend(f"{i}. {item['name']} — {item['game_id']}" for i, item in enumerate(requests, 1))
        await say(message, "stop", "\n".join(lines)[:3900])
        return

    # An owner's numeric reply to a registered participant's ID message announces their turn.
    if text.isdecimal() and reply:
        for dist in chat_state["distributions"].values():
            if dist["owner_id"] != user.id:
                continue
            participant = next((x for x in dist["requests"] if x["message_id"] == reply.message_id), None)
            if participant:
                await context.bot.send_message(
                    chat_id=chat.id,
                    text="وصل دورك ✅ اقبل وجون 🎉🤩",
                    reply_to_message_id=participant["message_id"],
                )
                return

    # Register ID only when replying to an active original distribution post.
    if reply:
        dist = get_distribution(chat.id, reply.message_id)
        if dist and dist["active"]:
            if user.id == dist["owner_id"]:
                return
            if any(item["user_id"] == user.id for item in dist["requests"]):
                await message.reply_text("💗 آيديك مسجل من قبل في هذا التوزيع.")
                return
            dist["requests"].append({
                "user_id": user.id,
                "name": display_name(user),
                "game_id": text,
                "message_id": message.message_id,
            })
            save_db()
            number = len(dist["requests"])
            await say(message, "request", f"👍 تم تسجيل الآيدي ورقمك هو {number}")


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.exception("Unhandled bot error", exc_info=context.error)


def main() -> None:
    if not TOKEN:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN environment variable")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & ~filters.COMMAND, handle_message))
    app.add_error_handler(on_error)
    log.info("RDO distribution bot is starting")
    app.run_polling(allowed_updates=Update.ALL_TYPES, bootstrap_retries=5)


if __name__ == "__main__":
    main()
