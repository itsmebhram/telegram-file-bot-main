# bot.py (Render-ready, webhook version)
import os
import logging
from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters, CallbackContext
import html
import time

# ---------- Config ----------
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "-1002909394259"))
ADMIN_ID = int(os.getenv("ADMIN_ID", "1317903617"))
USERS_FILE = os.getenv("USERS_FILE", "users.txt")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is missing!")

bot = Bot(BOT_TOKEN)

# ---------- Logging ----------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

file_count = 0

# ---------- Helper functions ----------
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

# ---------- Command Handlers ----------
def start(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    save_user(user_id)

    update.message.reply_text(
        "👋 Hi <b>ɮɦʀǟʍ ( ब्रह्म )</b>!\n\n"
        "✨ <b>Welcome to Free Storage Bot!</b> ✨\n\n"
        "Send me a file 📁 to store in our database and also you can get download link 🔗.\n"
        "🔗 Use the File ID or deep link to retrieve it anytime.\n\n"
        "📌 <b>Commands:</b>\n"
        "• /start – To check if I’m alive\n"
        "• /help – How to use\n\n"
        "⚠️ <b>Notice:</b> Do not upload any illegal or adult content, otherwise you’ll be <b>BANNED</b>.",
        parse_mode="HTML"
    )


def help_command(update: Update, context: CallbackContext) -> None:
    bot_username = context.bot.username
    update.message.reply_text(
        "📌 *How to Use this Bot:*\n\n"
        "1. Send any file (document, photo, video, etc).\n"
        "2. Receive a *File ID* and *deep link*.\n"
        "3. Use the File ID or link to get your file:\n\n"
        f"https://t.me/{bot_username}?start=<FileID>",
        parse_mode="MARKDOWN"
    )

def stats(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(
        f"📊 Total files saved this session: *{file_count}*",
        parse_mode="MARKDOWN"
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
            bot.copy_message(chat_id=int(uid), from_chat_id=announcement_msg.chat_id, message_id=announcement_msg.message_id)
            success += 1
            time.sleep(0.1)
        except Exception as e:
            logger.warning(f"Failed to send to {uid}: {e}")
            failed += 1

    update.message.reply_text(f"✅ Sent to {success} users.\n❌ Failed: {failed}")

def handle_file(update: Update, context: CallbackContext) -> None:
    global file_count
    message = update.message
    user_id = message.from_user.id
    save_user(user_id)

    if message.document or message.photo or message.video or message.audio:
        try:
            forwarded = message.forward(chat_id=GROUP_CHAT_ID)
            file_id = generate_file_id(user_id, forwarded.message_id)
            file_count += 1
            bot_username = context.bot.username
            message.reply_text(
                f"🎉 *File Uploaded!*\n\n"
                f"🔗 Direct Link:\n"
                f"`https://t.me/{bot_username}?start={file_id}`\n\n"
                f"🌟 Powered by @BhramsBots",
                parse_mode="MARKDOWN",
                disable_web_page_preview=True
            )
        except Exception as e:
            logger.error(f"Upload error: {e}")
            message.reply_text("❌ Failed to save your file. Try again.")

# ---------- Flask Webhook Setup ----------
app = Flask(__name__)

@app.route("/")
def index():
    return "Bot is running!", 200

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "ok", 200

# ---------- Dispatcher ----------
from telegram.ext import Dispatcher
dispatcher = Dispatcher(bot, None, workers=4)
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("help", help_command))
dispatcher.add_handler(CommandHandler("stats", stats))
dispatcher.add_handler(CommandHandler("announce", announce))
dispatcher.add_handler(MessageHandler(Filters.all & ~Filters.command, handle_file))

# ---------- Main ----------
if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=PORT)
