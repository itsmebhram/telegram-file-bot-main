# bot.py (Render-ready, webhook version)
import os
import logging
from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters, CallbackContext
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

# ---------- /start Handler ----------
def start(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    save_user(user_id)
    args = context.args  # if user clicked file link

    # --- If user clicked a file link ---
    if args:
        try:
            file_id = args[0]
            parts = file_id.split("_")
            if len(parts) == 3:
                _, original_user, message_id = parts
                original_user = int(original_user)
                message_id = int(message_id)

                bot.copy_message(chat_id=user_id, from_chat_id=GROUP_CHAT_ID, message_id=message_id)

                update.message.reply_text(
                    "📥 *Here’s your file!*\n"
                    "⚠️ Do not share this link publicly — it’s unique to your file.",
                    parse_mode="MARKDOWN"
                )
                return
            else:
                update.message.reply_text("⚠️ Invalid or expired link.")
                return
        except Exception as e:
            logger.error(f"Error retrieving file: {e}")
            update.message.reply_text("❌ File not found or may have been removed.")
            return

    # -------- Dynamic Username --------
    first = update.effective_user.first_name
    username = update.effective_user.username
    raw = first or username or "User"

    short_name = raw.strip().split()[0].capitalize()
    if len(short_name) > 20:
        short_name = short_name[:19] + "…"

    update.message.reply_text(
        f"👋 Hi <b>{short_name}</b>!\n\n"
        "✨ <b>Welcome to Free Storage Bot!</b> ✨\n\n"
        "Send me a file 📁 to store in our database and also you can get download link 🔗.\n"
        "🔗 Use the File ID or deep link to retrieve it anytime.\n\n"
        "📌 <b>Commands:</b>\n"
        "• /start – To check if I’m alive\n"
        "• /help – How to use\n\n"
        "⚠️ <b>Notice:</b> Do not upload any illegal or adult content, otherwise you’ll be <b>BANNED</b>.",
        parse_mode="HTML"
    )


# ---------- /announce Handler ----------
def announce(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        return update.message.reply_text("⛔ You are not an admin.")

    if not context.args:
        return update.message.reply_text("Usage: /announce Your message here")

    announcement_text = " ".join(context.args)

    if not os.path.exists(USERS_FILE):
        return update.message.reply_text("No users found.")

    update.message.reply_text("📢 Starting broadcast…")

    sent = 0
    failed = 0

    with open(USERS_FILE, "r") as f:
        users = [u.strip() for u in f if u.strip()]

    for user_id in users:
        try:
            bot.send_message(chat_id=int(user_id), text=announcement_text)
            sent += 1
            time.sleep(0.03)  # safe speed
        except Exception:
            failed += 1
            continue

    update.message.reply_text(
        f"✅ Broadcast Complete!\nSent: {sent}\nFailed: {failed}"
    )


# ---------- /help ----------
def help_command(update: Update, context: CallbackContext) -> None:
    bot_username = context.bot.username
    update.message.reply_text(
        "📌 *How to Use this Bot:*\n\n"
        "1. Send any file.\n"
        "2. Receive a File ID and deep link.\n"
        "3. Retrieve anytime using the link:\n\n"
        f"https://t.me/{bot_username}?start=<FileID>",
        parse_mode="MARKDOWN"
    )

# ---------- File Upload Handler ----------
def handle_file(update: Update, context: CallbackContext) -> None:
    global file_count
    message = update.message
    user_id = message.from_user.id
    save_user(user_id)

    try:
        copied_msg = bot.copy_message(
            chat_id=GROUP_CHAT_ID,
            from_chat_id=message.chat_id,
            message_id=message.message_id
        )

        file_id = generate_file_id(user_id, copied_msg.message_id)
        file_count += 1
        bot_username = context.bot.username

        link = f"https://t.me/{bot_username}?start={file_id}"

        message.reply_text(
            f"🎉 Your file is uploaded!\n\n"
            f"🔗 Direct Link:\n`{link}`",
            parse_mode="MARKDOWN",
            disable_web_page_preview=True
        )

    except Exception as e:
        logger.error(f"Upload error: {e}")
        message.reply_text("❌ Failed to save your file. Try again.")

# ---------- Flask Setup ----------
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
dispatcher = Dispatcher(bot, None, workers=4)
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("announce", announce))
dispatcher.add_handler(CommandHandler("help", help_command))
dispatcher.add_handler(MessageHandler(Filters.all & ~Filters.command, handle_file))

# ---------- Main ----------
if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=PORT)
