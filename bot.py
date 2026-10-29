#!/usr/bin/env python3
"""Telegram group announcement bot with hourly posting and admin-only /send."""
import asyncio
import html
import logging
import os
import re
from pathlib import Path

import yaml
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.yaml"

# Preserve the supplied announcement text and line breaks.
# Custom emoji are represented as HTML <tg-emoji emoji-id="...">...</tg-emoji>.
# A visible placeholder is used as the element's inner text; Telegram renders the
# custom emoji when the supplied ID is valid and supported for the bot/account.
ANNOUNCEMENT_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton(
        "لا تنسى اشتراك في قناة",
        url="https://t.me/rdranews",
        style="danger",
    )],
    [
        InlineKeyboardButton(
            "قوانين",
            url="https://t.me/rdranews/20",
            style="success",
        ),
        InlineKeyboardButton(
            "أخبار القروب",
            url="https://t.me/Telerroyalbot",
            style="success",
        ),
    ],
])

ANNOUNCEMENT_HTML = """اللملكة تقدم كل شي مجانا
‏ نوفر لكم جميع طلباتكم

<tg-emoji emoji-id="5231253712508297834">😀</tg-emoji> بكل مرة يجي تربل / دبل على الطبيعة نجهز سيرفر عينات لكم <tg-emoji emoji-id="5264771654466165028">😀</tg-emoji>

<tg-emoji emoji-id="5231253712508297834">😀</tg-emoji> بكل مرة يجي تربل / دبل على الكولكتر نجهز سيرفر كولكتر لكم <tg-emoji emoji-id="5465311846544207659">😀</tg-emoji>

<tg-emoji emoji-id="5231253712508297834">😀</tg-emoji> تدبيل بيعات طوال الوقت وخصوصاً اذا فيه تربل او دبل على التاجر، وكذلك نجهز سيرفرات جلود للتاجر <tg-emoji emoji-id="5197620270289931332">😀</tg-emoji><tg-emoji emoji-id="5361623471933644138">😀</tg-emoji>

<tg-emoji emoji-id="5231253712508297834">😀</tg-emoji> نجهز سيرفرات جلود سواء ملابس Gus أو الجلود الاسطورية <tg-emoji emoji-id="5355237804752254088">😀</tg-emoji> <tg-emoji emoji-id="5354797630733955999">😀</tg-emoji>

<tg-emoji emoji-id="5231253712508297834">😀</tg-emoji> تأفيك لجميع أنواع كنوز <tg-emoji emoji-id="5431573577059034585">😀</tg-emoji> <tg-emoji emoji-id="5395765764697369708">😀</tg-emoji>

<tg-emoji emoji-id="5231253712508297834">😀</tg-emoji> نسوي تجمعات وفعاليات ومسابقات للأعضاء <tg-emoji emoji-id="5461151367559141950">😀</tg-emoji> <tg-emoji emoji-id="5951976197171711978">😀</tg-emoji> <tg-emoji emoji-id="5440539497383087970">😀</tg-emoji>

<tg-emoji emoji-id="5231253712508297834">😀</tg-emoji> نقدم لكم قلتش اسلحه ايضاً وجميع قلتشات لعبه <tg-emoji emoji-id="5408935401442267103">😀</tg-emoji> <tg-emoji emoji-id="5246920176951111662">😀</tg-emoji>

 <tg-emoji emoji-id="5391111433192778188">😀</tg-emoji> إدارة القروب <tg-emoji emoji-id="5391111433192778188">😀</tg-emoji>"""


# الإعلان الثاني مستقل عن الإعلان الأول، مع الإيموجي المخصص المطلوب.
SECOND_ANNOUNCEMENT_HTML = """عند وجود أي مخالفة أو مشكلة داخل القروب،
يرجى ذكر الإدارة مباشرة عبر [@admin]، وسيتم مراجعة البلاغ واتخاذ الإجراء المناسب."""
SECOND_ANNOUNCEMENT_HTML = SECOND_ANNOUNCEMENT_HTML.replace(
    "عند وجود أي مخالفة أو مشكلة داخل القروب،",
    '<tg-emoji emoji-id="5341633328338451873">⚠️</tg-emoji> عند وجود أي مخالفة أو مشكلة داخل القروب،',
)

SECOND_ANNOUNCEMENT_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("قوانين", url="https://t.me/rdranews/20")],
])

# Gold menu: colored markers are used because Telegram does not expose
# per-inline-button background colors through the standard Bot API.
GOLD_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("❄️ لاكي ايزيبلا", url="https://t.me/rdranews/28", api_kwargs={"style": "danger"})],
    [InlineKeyboardButton("🌊 خريطة الشلال", url="https://t.me/rdranews/29", api_kwargs={"style": "danger"})],
    [InlineKeyboardButton("🪨 خريطة الصخرة", url="https://t.me/rdranews/30", api_kwargs={"style": "danger"})],
    [InlineKeyboardButton("🗺️ خريطة الجسر", url="https://t.me/rdranews/32", api_kwargs={"style": "danger"})],
    [InlineKeyboardButton("🗺️ قلتش تدبيل خرائط", url="https://t.me/rdranews/31", api_kwargs={"style": "primary"})],
])


async def send_second_announcement(bot, chat_id: int):
    await bot.send_message(
        chat_id=chat_id,
        text=SECOND_ANNOUNCEMENT_HTML,
        parse_mode=ParseMode.HTML,
        reply_markup=SECOND_ANNOUNCEMENT_KEYBOARD,
        disable_web_page_preview=True,
    )

async def scheduled_post_second(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.application.bot_data["group_id"]
    try:
        await send_second_announcement(context.bot, chat_id)
        logging.info("Scheduled second announcement sent to %s", chat_id)
    except TelegramError:
        logging.exception("Scheduled second announcement failed")

def load_config():
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    cfg["bot_token"] = os.getenv("BOT_TOKEN", cfg.get("bot_token", ""))
    cfg["group_id"] = os.getenv("GROUP_ID", cfg.get("group_id", ""))
    cfg["interval_seconds"] = int(os.getenv("INTERVAL_SECONDS", cfg.get("interval_seconds", 3600)))
    if not cfg["bot_token"] or cfg["bot_token"] == "PUT_BOT_TOKEN_HERE":
        raise RuntimeError("ضع توكن البوت في config.yaml أو متغير البيئة BOT_TOKEN.")
    if str(cfg["group_id"]) in ("", "PUT_GROUP_ID_HERE"):
        raise RuntimeError("ضع رقم القروب في config.yaml أو متغير البيئة GROUP_ID.")
    if cfg["interval_seconds"] < 60:
        raise RuntimeError("مدة التكرار يجب أن تكون 60 ثانية على الأقل.")
    cfg["group_id"] = int(cfg["group_id"])
    return cfg

async def send_announcement(bot, chat_id: int):
    await bot.send_message(
        chat_id=chat_id,
        text=ANNOUNCEMENT_HTML,
        parse_mode=ParseMode.HTML,
        reply_markup=ANNOUNCEMENT_KEYBOARD,
        disable_web_page_preview=True,
    )

async def scheduled_post(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.application.bot_data["group_id"]
    try:
        await send_announcement(context.bot, chat_id)
        logging.info("Scheduled announcement sent to %s", chat_id)
    except TelegramError:
        logging.exception("Scheduled announcement failed")

async def start_scheduler(app: Application):
    interval = app.bot_data["interval_seconds"]
    # First automatic post occurs after one full interval.
    app.job_queue.run_repeating(scheduled_post, interval=interval, first=interval, name="hourly_announcement")
    app.job_queue.run_repeating(
        scheduled_post_second,
        interval=10800,
        first=10800,
        name="second_announcement_3h",
    )
    logging.info("Scheduler configured: first every %s seconds; second every 10800 seconds", interval)

async def send_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat or not update.effective_user:
        return
    # Only allow the command in the configured group and only for its administrators.
    if update.effective_chat.id != context.application.bot_data["group_id"]:
        await update.effective_message.reply_text("هذا الأمر مخصص لقروب الإعلان المحدد فقط.")
        return
    try:
        member = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
    except TelegramError:
        logging.exception("Could not verify administrator status")
        await update.effective_message.reply_text("تعذر التحقق من صلاحياتك. حاول لاحقًا.")
        return
    if member.status not in ("administrator", "creator"):
        await update.effective_message.reply_text("عذرًا، هذا الأمر للمشرفين فقط.")
        return
    try:
        await send_announcement(context.bot, context.application.bot_data["group_id"])
        await update.effective_message.reply_text("تم إرسال الإعلان.")
    except TelegramError:
        logging.exception("Manual announcement failed")
        await update.effective_message.reply_text("تعذر إرسال الإعلان. راجع سجل الخدمة وصلاحيات البوت.")


async def send2_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat or not update.effective_user or not update.effective_message:
        return
    if update.effective_chat.id != context.application.bot_data["group_id"]:
        await update.effective_message.reply_text("هذا الأمر مخصص لقروب الإعلان المحدد فقط.")
        return
    try:
        member = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
    except TelegramError:
        logging.exception("Could not verify administrator status for /send2")
        await update.effective_message.reply_text("تعذر التحقق من صلاحياتك. حاول لاحقًا.")
        return
    if member.status not in ("administrator", "creator"):
        await update.effective_message.reply_text("عذرًا، هذا الأمر للمشرفين فقط.")
        return
    try:
        await send_second_announcement(context.bot, context.application.bot_data["group_id"])
        await update.effective_message.reply_text("تم إرسال الإعلان الثاني.")
    except TelegramError:
        logging.exception("Manual second announcement failed")
        await update.effective_message.reply_text("تعذر إرسال الإعلان الثاني. راجع سجل الخدمة وصلاحيات البوت.")

# Auto-reply to standalone greetings in the configured group only.
GREETING_CUSTOM_EMOJI_ID = "5429414269366072780"

def normalize_greeting(text: str) -> str:
    """Normalize common Arabic spelling/punctuation variations for greeting matching."""
    text = re.sub(r"[\u064B-\u065F\u0670\u0640]", "", text)  # diacritics and tatweel
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    text = re.sub(r"هلا+", "هلا", text)
    return " ".join(text.split()).casefold()

def greeting_reply(text: str):
    normalized = normalize_greeting(text)
    # Match whole greeting phrases, not arbitrary messages that merely contain them.
    greetings = {
        "هلا": "هلا وسهلا",
        "هلا والله": "هلا وسهلا",
        "مرحبا": "يا مرحبا وسهلا",
        "مرحبا بكم": "يا مرحبا وسهلا",
        "السلام عليكم": "وعليكم السلام ورحمة الله وبركاته",
        "سلام عليكم": "وعليكم السلام ورحمة الله وبركاته",
        "السلام عليكم ورحمة الله وبركاته": "وعليكم السلام ورحمة الله وبركاته",
    }
    return greetings.get(normalized)

async def greeting_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not message or not chat or not user:
        return
    # This feature only applies to standalone messages in the configured group.
    if chat.id != context.application.bot_data.get("group_id"):
        return
    if message.reply_to_message is not None:
        return
    if user.is_bot:
        return
    if not message.text:
        return

    # Respond to the standalone keyword "ذهب" in the configured group.
    if message.text.strip() == "ذهب":
        photo_path = ROOT / "gold_menu.jpg"
        try:
            with photo_path.open("rb") as photo:
                await message.reply_photo(
                    photo=photo,
                    reply_markup=GOLD_KEYBOARD,
                )
        except (OSError, TelegramError):
            logging.exception("Gold menu could not be sent")
        return

    reply = greeting_reply(message.text)
    if not reply:
        return

    # Numeric IDs in this format are Telegram custom-emoji IDs, not sticker file_ids.
    # Telegram renders the custom emoji when this ID is valid and available to the bot.
    safe_name = html.escape(user.full_name)
    response = (
        f"{html.escape(reply)}\n"
        f"ارحــب {safe_name} "
        f'<tg-emoji emoji-id="{GREETING_CUSTOM_EMOJI_ID}">👑</tg-emoji>'
    )
    try:
        await message.reply_text(response, parse_mode=ParseMode.HTML)
    except TelegramError:
        logging.exception("Greeting auto-reply failed")


async def post_init(app: Application):
    cfg = load_config()
    app.bot_data["group_id"] = cfg["group_id"]
    app.bot_data["interval_seconds"] = cfg["interval_seconds"]
    await start_scheduler(app)

def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.StreamHandler()],
    )
    cfg = load_config()
    app = (
        Application.builder()
        .token(cfg["bot_token"])
        .post_init(post_init)
        .build()
    )
    app.add_handler(CommandHandler("send", send_command))
    app.add_handler(CommandHandler("send2", send2_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, greeting_message_handler))
    logging.info("Starting announcement bot")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
