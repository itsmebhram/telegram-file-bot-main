# bot.py
import os
import logging
import time
import html
from uuid import uuid4
from flask import Flask
from telegram import Update, Message, ParseMode
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

# ---------- Config (safe: read from environment) ----------
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "-1002909394259"))
ADMIN_ID = int(os.getenv("ADMIN_ID", "1317903617"))
USERS_FILE = os.getenv("USERS_FILE", "users.txt")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is missing!")

# ---------- Logging ----------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

file_count = 0


def generate_file_id(user_id: int, message_id: int) -> str:
    timestamp = int(time.time())
    return f"{timestamp}_{user_id}_{message_id}"


def save_user(user_id: int) -> None:
    try:
        users = set()
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, "r") as f:
                users = set(line.strip() for line in f if line.strip())
        if str(user_id) not in users:
            with open(USERS_FILE, "a") as f:
                f.write(f"{user_id}\n")
    except Exception as e:
        logger.error(f"Error saving user {user_id}: {e}")


def start(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    save_user(user_id)

    args = context.args
    if args and len(args) == 1:
        try:
            parts = args[0].split("_")
            if len(parts) == 3:
                message_id = int(parts[2])
                context.bot.copy_message(
                    chat_id=update.effective_chat.id,
                    from_chat_id=GROUP_CHAT_ID,
                    message_id=message_id
                )
                return
        except Exception:
            update.message.reply_text("❌ Invalid deep link.")
            return

    update.message.reply_text(
        f"👋 Hi <b>{update.effective_user.first_name}</b>!\n\n"
        "✨ <b>Welcome to Free Storage Bot!</b> ✨\n\n"
        "📁 Upload any file and get a unique <b>File ID</b>.\n"
        "🔗 Use the File ID or deep link to retrieve it anytime.\n\n"
        "<b>📌 Commands:</b>\n"
        "• /help – How to use\n"
        "• /stats – Session Stats\n"
        "• /announce – (Admin only) Broadcast message (reply to a message)",
        parse_mode=ParseMode.HTML
    )


def help_command(update: Update, context: CallbackContext) -> None:
    bot_username = context.bot.username
    update.message.reply_text(
        "📌 *How to Use this Bot:*\n\n"
        "1. Send any file (document, photo, video, etc).\n"
        "2. Receive a *File ID* and *deep link*.\n"
        "3. Use the File ID or link to get your file:\n\n"
        f"https://t.me/{bot_username}?start=<FileID>\n\n"
        "4. Admins can broadcast announcements with /announce.",
        parse_mode=ParseMode.MARKDOWN
    )


def stats(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(
        f"📊 Total files saved this session: *{file_count}*",
        parse_mode=ParseMode.MARKDOWN
    )


def announce(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    if user_id != ADMIN_ID:
        update.message.reply_text("❌ You are not authorized to use this command.")
        return
    if not update.message.reply_to_message:
        update.message.reply_text("❌ You must reply to a message to announce it.")
        return

    try:
        with open(USERS_FILE, "r") as f:
            users = set(line.strip() for line in f if line.strip())
    except FileNotFoundError:
        update.message.reply_text("❌ No users found to announce to.")
        return

    announcement_msg = update.message.reply_to_message
    success, failed = 0, 0

    for uid in users:
        try:
            send_announcement_to_user(context.bot, int(uid), announcement_msg)
            success += 1
            time.sleep(0.1)
        except Exception as e:
            logger.warning(f"Failed to send to {uid}: {e}")
            failed += 1

    update.message.reply_text(
        f"✅ Sent to {success} users.\n❌ Failed: {failed}"
    )


def send_announcement_to_user(bot, chat_id: int, message: Message) -> None:
    try:
        if message.text:
            bot.send_message(chat_id=chat_id, text=message.text, parse_mode=ParseMode.MARKDOWN)
        elif message.photo:
            bot.send_photo(chat_id=chat_id, photo=message.photo[-1].file_id,
                           caption=message.caption or "", parse_mode=ParseMode.MARKDOWN)
        elif message.video:
            bot.send_video(chat_id=chat_id, video=message.video.file_id,
                           caption=message.caption or "", parse_mode=ParseMode.MARKDOWN)
        elif message.document:
            bot.send_document(chat_id=chat_id, document=message.document.file_id,
                              caption=message.caption or "", parse_mode=ParseMode.MARKDOWN)
        elif message.audio:
            bot.send_audio(chat_id=chat_id, audio=message.audio.file_id,
                           caption=message.caption or "", parse_mode=ParseMode.MARKDOWN)
        elif message.voice:
            bot.send_voice(chat_id=chat_id, voice=message.voice.file_id,
                           caption=message.caption or "", parse_mode=ParseMode.MARKDOWN)
        elif message.video_note:
            bot.send_video_note(chat_id=chat_id, video_note=message.video_note.file_id)
        else:
            text = message.caption or message.text or ""
            if text:
                bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.warning(f"send_announcement_to_user error for {chat_id}: {e}")


def handle_file(update: Update, context: CallbackContext) -> None:
    global file_count
    message = update.message
    user_id = message.from_user.id
    if message.from_user.is_bot:
        return

    save_user(user_id)

    if (message.document or message.photo or message.video or message.audio or
            message.voice or message.video_note):
        try:
            forwarded = message.forward(chat_id=GROUP_CHAT_ID)
            file_id = generate_file_id(user_id, forwarded.message_id)
            file_count += 1

            file_type = "File"
            file_name = "Unnamed"
            file_size = 0

            if message.document:
                file_type = "Document"
                file_name = message.document.file_name or "Document"
                file_size = message.document.file_size
            elif message.video:
                file_type, file_name, file_size = "Video", "Video", message.video.file_size
            elif message.audio:
                file_type, file_name, file_size = "Audio", "Audio", message.audio.file_size
            elif message.photo:
                file_type, file_name = "Photo", "Photo"
            elif message.voice:
                file_type, file_name, file_size = "Voice", "Voice", message.voice.file_size
            elif message.video_note:
                file_type, file_name = "Video Note", "Video Note"

            size_mb = round(file_size / (1024 * 1024), 2) if file_size else "?"
            bot_username = context.bot.username
            message.reply_text(
                f"🎉 *Hurray !! Your File has been Uploaded to Our Server*\n\n"
                f"📂 *File Name:* `{html.escape(file_name)}`\n"
                f"📊 *File Size:* {size_mb} MB\n\n"
                f"🔗 *Here is Your Direct Link:* \n"
                f"`https://t.me/{bot_username}?start={file_id}`\n\n"
                f"🌟 Powered By @BhramsBots\n\n"
                f"📁 *Type:* {file_type}\n"
                f"🚸 *Note:* Your Link is Stored Safely Until Admins Action !",
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True
            )
        except Exception as e:
            logger.error(f"Upload error: {e}")
            message.reply_text("❌ Failed to save your file. Please try again.")
    elif message.text:
        try:
            parts = message.text.strip().split("_")
            if len(parts) == 3:
                message_id = int(parts[2])
                context.bot.copy_message(
                    chat_id=update.effective_chat.id,
                    from_chat_id=GROUP_CHAT_ID,
                    message_id=message_id
                )
            else:
                raise ValueError
        except Exception:
            message.reply_text("❌ Invalid File ID. Please check and try again.")


def unknown_command(update: Update, context: CallbackContext) -> None:
    update.message.reply_text("❓ Unknown command. Use /help for available commands.")


# ---------- Flask keep-alive ----------
app = Flask(__name__)

@app.route("/")
def home():
    return "OK", 200


# ---------- Main ----------
def main() -> None:
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help_command))
    dp.add_handler(CommandHandler("stats", stats))
    dp.add_handler(CommandHandler("announce", announce))
    dp.add_handler(MessageHandler(Filters.all & ~Filters.command, handle_file))
    dp.add_handler(MessageHandler(Filters.command, unknown_command))

    logger.info("🤖 Bot starting (polling)...")
    updater.start_polling()

    port = int(os.getenv("PORT", "8080"))
    logger.info(f"Flask listening on port {port}")
    app.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
