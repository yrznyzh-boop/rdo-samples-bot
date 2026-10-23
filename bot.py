import json
import os
import random
import logging
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
DATA_FILE = Path("subscribers.json")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

AZKAR = [
    "سُبْحَانَ اللَّهِ وَبِحَمْدِهِ، سُبْحَانَ اللَّهِ الْعَظِيمِ.",
    "أَسْتَغْفِرُ اللَّهَ وَأَتُوبُ إِلَيْهِ.",
    "لَا إِلَهَ إِلَّا اللَّهُ وَحْدَهُ لَا شَرِيكَ لَهُ، لَهُ الْمُلْكُ وَلَهُ الْحَمْدُ وَهُوَ عَلَى كُلِّ شَيْءٍ قَدِيرٌ.",
    "اللَّهُمَّ صَلِّ وَسَلِّمْ عَلَى نَبِيِّنَا مُحَمَّدٍ.",
    "سُبْحَانَ اللَّهِ، وَالْحَمْدُ لِلَّهِ، وَلَا إِلَهَ إِلَّا اللَّهُ، وَاللَّهُ أَكْبَرُ.",
    "لَا حَوْلَ وَلَا قُوَّةَ إِلَّا بِاللَّهِ.",
    "رَضِيتُ بِاللَّهِ رَبًّا، وَبِالْإِسْلَامِ دِينًا، وَبِمُحَمَّدٍ ﷺ نَبِيًّا.",
    "اللَّهُمَّ اغْفِرْ لِي وَارْحَمْنِي وَاهْدِنِي وَعَافِنِي وَارْزُقْنِي.",
]


def load_subscribers():
    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        return set(int(chat_id) for chat_id in data)
    except (FileNotFoundError, json.JSONDecodeError, TypeError, ValueError):
        return set()


def save_subscribers(chat_ids):
    DATA_FILE.write_text(json.dumps(sorted(chat_ids)), encoding="utf-8")


subscribers = load_subscribers()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat:
        return
    subscribers.add(chat.id)
    save_subscribers(subscribers)
    await update.effective_message.reply_text(
        "🌙 تم تفعيل أذكار DailyAzkarBot!\n"
        "سأرسل الأذكار 5 مرات يوميًا على مدار 24 ساعة.\n\n"
        "الأوامر:\n/azkar_now — إرسال ذكر الآن\n/stop_azkar — إيقاف الأذكار"
    )


async def stop_azkar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat:
        return
    subscribers.discard(chat.id)
    save_subscribers(subscribers)
    await update.effective_message.reply_text("تم إيقاف رسائل الأذكار لهذه المحادثة. لإعادة التفعيل أرسل /start")


async def send_azkar_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text("🌿 ذكر الله يطمئن القلوب\n\n" + random.choice(AZKAR))


async def send_daily_azkar(context: ContextTypes.DEFAULT_TYPE):
    message = "🌿 تذكير بذكر الله\n\n" + random.choice(AZKAR)
    for chat_id in list(subscribers):
        try:
            await context.bot.send_message(chat_id=chat_id, text=message)
        except Exception as exc:
            logger.warning("Could not send to chat %s: %s", chat_id, exc)


def schedule_five_daily_messages(app: Application):
    job_queue = app.job_queue
    if job_queue is None:
        raise RuntimeError("JobQueue is unavailable. Check requirements.txt")
    # Pick five distinct times spread across the full UTC day.
    minutes = sorted(random.sample(range(24 * 60), 5))
    for index, minute_of_day in enumerate(minutes):
        hour, minute = divmod(minute_of_day, 60)
        job_queue.run_daily(
            send_daily_azkar,
            time=time(hour=hour, minute=minute, tzinfo=timezone.utc),
            name=f"daily_azkar_{index}",
        )
    logger.info("Scheduled five daily messages at UTC minutes: %s", minutes)


async def post_init(app: Application):
    schedule_five_daily_messages(app)


def main():
    if not TOKEN:
        raise RuntimeError("Set BOT_TOKEN as an environment variable before starting the bot.")
    app = Application.builder().token(TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop_azkar", stop_azkar))
    app.add_handler(CommandHandler("azkar_now", send_azkar_now))
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
