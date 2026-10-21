# RDO Distribution Telegram Bot

## Hosting configuration
- Runtime: Python 3.10 or newer
- Start command: `python main.py`
- Required environment variable: `TELEGRAM_BOT_TOKEN`
- Dependency file: `requirements.txt`

Do not put the bot token in this repository. Add it only in your hosting provider's secret/environment-variable settings.

## Group setup
1. Add the bot to the group.
2. In BotFather, run `/setprivacy`, select this bot, and choose **Disable** so it can read ordinary group replies.
3. If the hosting provider offers a persistent disk, mount it and set `DATA_FILE` to a path on that disk. Otherwise the JSON file may be lost when the host recreates the container.
4. Keep only one running instance using polling for this bot token. Do not run the same token in another bot process at the same time.

## Usage
- Owner sends an ordinary original message in the group.
- Owner replies to that original message with `توزيع`.
- Members reply to that same original message with their game ID.
- Owner replies to the original message with `قائمة` to list entries.
- Owner replies to the original message with `وقف توزيع` to close that distribution.
- Owner replies to a participant's registered ID message with any number to announce their turn.

Each original message has its own independent distribution, so multiple distributions can run in one group.

## Optional stickers
Set `STICKER_START`, `STICKER_REQUEST`, `STICKER_TURN`, `STICKER_STOP`, or `STICKER_LIST` to Telegram sticker `file_id` values. Without them, the bot sends text messages. Telegram stickers cannot be embedded inline inside a text list; they must be sent as separate messages.

## Notes
- The bot stores data in `data.json` beside the application by default. Use persistent storage on the host if available.
- The code logs startup and runtime errors to the host logs.
