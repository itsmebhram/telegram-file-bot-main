# bot.py (Render-ready, webhook version)
import os
import logging
import requests
from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters, CallbackContext
import time

# ---------- Config ----------
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "-1002909394259"))
ADMIN_ID = int(os.getenv("ADMIN_ID", "1317903617"))
USERS_FILE = os.getenv("USERS_FILE", "users.txt")
BANNED_FILE = "banned.txt"

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

# ---------- Helper Functions ----------
def generate_file_id(user_id: int, message_id: int) -> str:
    timestamp = int(time.time())
    return f"{timestamp}_{user_id}_{message_id}"

def save_user(user_id: int) -> None:
    if not os.path.exists(USERS_FILE):
        open(USERS_FILE, "w").close()

    with open(USERS_FILE, "r") as f:
        users = set(line.strip() for line in f if line.strip())

    if str(user_id) not in users:
        with open(USERS_FILE, "a") as f:
            f.write(f"{user_id}\n")

def load_banned():
    if not os.path.exists(BANNED_FILE):
        return set()
    with open(BANNED_FILE, "r") as f:
        return set(line.strip() for line in f if line.strip())

def save_banned(user_id):
    banned = load_banned()
    if str(user_id) not in banned:
        with open(BANNED_FILE, "a") as f:
            f.write(f"{user_id}\n")

def is_banned(user_id):
    return str(user_id) in load_banned()

# ---------- URL Upload Handler ----------
def handle_url_upload(update: Update, context: CallbackContext):
    message = update.message
    user_id = message.from_user.id
    url = message.text.strip()

    # Notify user
    message.reply_text("📥 Downloading file from URL, please wait…")

    try:
        r = requests.get(url, allow_redirects=True, timeout=20)
        if r.status_code != 200:
            return message.reply_text("❌ Failed to download file from the provided URL.")

        filename = url.split("/")[-1] or "file"
        temp_path = f"/tmp/{filename}"

        with open(temp_path, "wb") as f:
            f.write(r.content)

        # Upload to your storage group
        sent = bot.send_document(
            chat_id=GROUP_CHAT_ID,
            document=open(temp_path, "rb")
        )

        file_id = generate_file_id(user_id, sent.message_id)
        bot_username = context.bot.username
        link = f"https://t.me/{bot_username}?start={file_id}"

        # Reply to user
        message.reply_text(
            f"🎉 *Your URL File is Uploaded Successfully!*\n\n"
            f"📂 *File:* `{filename}`\n"
            f"🔗 *Direct Link:* `{link}`\n",
            parse_mode="MARKDOWN"
        )

        os.remove(temp_path)

    except Exception as e:
        logger.error(f"URL upload error: {e}")
        message.reply_text("❌ Could not download file. URL may be invalid.")

# ---------- /start ----------
def start(update: Update, context: CallbackContext) -> None:
    # Banned users blocked
    if is_banned(update.effective_user.id):
        return update.message.reply_text("⛔ You are banned from using this bot because of inappropriate uploads.")

    user_id = update.effective_user.id
    save_user(user_id)
    args = context.args

    # Deep-link file download
    if args:
        try:
            file_id = args[0]
            parts = file_id.split("_")
            if len(parts) == 3:
                _, orig_user, message_id = parts
                bot.copy_message(
                    chat_id=user_id,
                    from_chat_id=GROUP_CHAT_ID,
                    message_id=int(message_id)
                )
                return update.message.reply_text(
                    "📥 *Here’s your file!*\n⚠️ Do not share this link.",
                    parse_mode="MARKDOWN"
                )
            else:
                return update.message.reply_text("⚠️ Invalid or expired link.")
        except:
            return update.message.reply_text("❌ File not found or removed.")

    first = update.effective_user.first_name
    username = update.effective_user.username
    raw = first or username or "User"
    short_name = raw.strip().split()[0].capitalize()[:20]

    update.message.reply_text(
        f"👋 Hi <b>{short_name}</b>!\n\n"
        "✨ <b>Welcome to Free Storage Bot!</b> ✨\n\n"
        "Send any file 📁 or URL 🔗 to store it safely.\n"
        "Retrieve anytime using deep links.\n\n"
        "📌 Commands:\n/start\n/help\n",
        parse_mode="HTML"
    )

# ---------- /announce ----------
def announce(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        return update.message.reply_text("⛔ Admin only.")

    if not context.args:
        return update.message.reply_text("Usage: /announce message")

    msg = " ".join(context.args)

    with open(USERS_FILE, "r") as f:
        users = [u.strip() for u in f if u.strip()]

    sent, failed = 0, 0
    update.message.reply_text("📢 Broadcasting…")

    for uid in users:
        try:
            bot.send_message(uid, msg)
            sent += 1
            time.sleep(0.03)
        except:
            failed += 1

    update.message.reply_text(f"✅ Done!\nSent: {sent}\nFailed: {failed}")

# ---------- Ban Commands ----------
def ban(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        return update.message.reply_text("⛔ Admin only.")

    if not context.args:
        return update.message.reply_text("Usage: /ban user_id")

    uid = context.args[0]
    save_banned(uid)
    update.message.reply_text(f"🚫 User {uid} banned.")

def unban(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        return update.message.reply_text("⛔ Admin only.")

    if not context.args:
        return update.message.reply_text("Usage: /unban user_id")

    uid = context.args[0]
    banned = load_banned()

    if uid in banned:
        banned.remove(uid)
        with open(BANNED_FILE, "w") as f:
            f.write("\n".join(banned))
        update.message.reply_text(f"✅ User {uid} unbanned.")
    else:
        update.message.reply_text("User not banned.")

# ---------- /help ----------
def help_command(update: Update, context: CallbackContext):
    bot_username = context.bot.username
    update.message.reply_text(
        "📌 *Bot Guide:*\n\n"
        "• Send any file to upload\n"
        "• Send any URL to upload its file\n"
        "• Retrieve stored files anytime using:\n"
        f"https://t.me/{bot_username}?start=<FileID>",
        parse_mode="MARKDOWN"
    )

# ---------- File Upload Handler ----------
def handle_file(update: Update, context: CallbackContext) -> None:
    global file_count
    message = update.message

    # ⭐ URL upload detection
    if message.text and message.text.startswith("http"):
        return handle_url_upload(update, context)

    user_id = message.from_user.id

    if is_banned(user_id):
        return message.reply_text("⛔ You are banned.")

    save_user(user_id)

    user_name = message.from_user.full_name or message.from_user.username or "Unknown User"

    try:
        # Identity report
        bot.send_message(
            GROUP_CHAT_ID,
            f"📨 <b>New Upload</b>\n👤 {user_name}\n🆔 <code>{user_id}</code>",
            parse_mode="HTML"
        )

        # Copy to storage
        copied_msg = bot.copy_message(
            GROUP_CHAT_ID,
            message.chat_id,
            message.message_id
        )

        # Generate link
        file_id = generate_file_id(user_id, copied_msg.message_id)
        file_count += 1
        bot_username = context.bot.username
        link = f"https://t.me/{bot_username}?start={file_id}"

        # Extract file details
        file_name = "Unknown"
        file_size = "Unknown"
        file_type = "Media"

        if message.document:
            file_name = message.document.file_name
            file_size = f"{round(message.document.file_size/1024/1024,2)} MB"
            file_type = "Document"
        elif message.photo:
            file_name = "Photo"
            file_type = "Photo"
        elif message.video:
            file_name = "Video"
            file_size = f"{round(message.video.file_size/1024/1024,2)} MB"
            file_type = "Video"
        elif message.audio:
            file_name = message.audio.file_name or "Audio"
            file_size = f"{round(message.audio.file_size/1024/1024,2)} MB"
            file_type = "Audio"

        # Reply
        message.reply_text(
            f"🎉 *Hurray !! Your File has been Uploaded to Our Server*\n\n"
            f"📂 *File Name:* `{file_name}`\n"
            f"📊 *File Size:* {file_size}\n"
            f"📁 *Type:* {file_type}\n\n"
            f"🔗 *Direct Link:* `{link}`\n\n"
            f"🌟 *Powered By* @BhramsBots",
            parse_mode="MARKDOWN",
            disable_web_page_preview=True
        )

    except Exception as e:
        logger.error(f"Upload error: {e}")
        message.reply_text("❌ Upload failed. Try again.")

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
dispatcher.add_handler(CommandHandler("ban", ban))
dispatcher.add_handler(CommandHandler("unban", unban))
dispatcher.add_handler(CommandHandler("help", help_command))
dispatcher.add_handler(MessageHandler(Filters.all & ~Filters.command, handle_file))

# ---------- Main ----------
if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=PORT)
