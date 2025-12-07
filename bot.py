# bot.py (Render-ready, webhook version)
import os
import logging
import requests
import tempfile
import time
from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters, CallbackContext

# ---------- Config ----------
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "-1002909394259"))
ADMIN_ID = int(os.getenv("ADMIN_ID", "1317903617"))
USERS_FILE = os.getenv("USERS_FILE", "users.txt")
BANNED_FILE = "banned.txt"
HISTORY_FILE = "history.txt"

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

# ---------- HISTORY ----------
def save_history(user_id, file_name, link):
    if not os.path.exists(HISTORY_FILE):
        open(HISTORY_FILE, "w").close()

    with open(HISTORY_FILE, "a") as f:
        f.write(f"{user_id}|{file_name}|{link}\n")

def get_user_history(user_id, limit=5):
    if not os.path.exists(HISTORY_FILE):
        return []

    with open(HISTORY_FILE, "r") as f:
        lines = [line.strip() for line in f if line.strip()]

    records = [l for l in lines if l.startswith(str(user_id) + "|")]
    return records[-limit:]

# ---------- URL validation ----------
VALID_EXTENSIONS = (
    ".pdf", ".zip", ".rar", ".7z",
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp",
    ".mp4", ".mkv", ".avi", ".mov",
    ".mp3", ".wav", ".ogg",
    ".apk",
    ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".txt", ".epub", ".csv"
)

def is_direct_file_url(url: str) -> bool:
    if not url:
        return False
    url_lower = url.lower().split('?')[0].split('#')[0]
    return any(url_lower.endswith(ext) for ext in VALID_EXTENSIONS)

# ---------- Download helper ----------
def download_file_from_url(url: str, timeout: int = 30):
    """
    Downloads a URL to a temporary file (streaming). Returns (temp_path, filename) or (None, None).
    """
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; StorageBot/1.0)"}
        r = requests.get(url, stream=True, timeout=timeout, headers=headers, allow_redirects=True)
        if r.status_code != 200:
            logger.warning(f"URL download returned status {r.status_code} for {url}")
            return None, None

        # Try to guess filename
        filename = url.split("/")[-1].split("?")[0].split("#")[0] or f"file_{int(time.time())}"

        # If Content-Disposition header present, try to extract actual name
        cd = r.headers.get("content-disposition")
        if cd and "filename=" in cd:
            try:
                part = cd.split("filename=")[-1].strip()
                filename = part.strip('\"\' ')
            except:
                pass

        # create temporary file
        tmp = tempfile.NamedTemporaryFile(delete=False, prefix="dl_", suffix=f"_{filename}")
        tmp_path = tmp.name
        tmp.close()

        # stream download
        with open(tmp_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        return tmp_path, filename

    except Exception as e:
        logger.error(f"download_file_from_url error: {e}")
        return None, None

# ---------- URL Handler ----------
def handle_url(update: Update, context: CallbackContext):
    message = update.message
    if not message or not message.text:
        return

    url = message.text.strip()

    # only http/https
    if not (url.startswith("http://") or url.startswith("https://")):
        return

    # Only accept direct file URLs (by extension)
    if not is_direct_file_url(url):
        return message.reply_text(
            "⚠️ This is not a direct file link.\n\n"
            "Please send URLs that end with a file extension, for example:\n"
            ".pdf .mp4 .mp3 .jpg .png .zip .apk\n\n"
            "Links to webpages, gallery pages, or services (Drive, YouTube) are not supported here."
        )

    user_id = message.from_user.id

    if is_banned(user_id):
        return message.reply_text("⛔ You are banned from using this bot.")

    # Send temporary "downloading" message
    try:
        waiting_msg = message.reply_text("⬇️ Downloading from URL, please wait...")
    except Exception:
        waiting_msg = None

    temp_path, filename = download_file_from_url(url)
    if not temp_path:
        if waiting_msg:
            try: waiting_msg.delete()
            except: pass
        return message.reply_text("❌ Failed to download file from URL. The link may be invalid or blocked.")

    # Upload to storage group (try as document; handle large files)
    try:
        with open(temp_path, "rb") as fh:
            sent = bot.send_document(chat_id=GROUP_CHAT_ID, document=fh, caption=f"Uploaded via URL by {message.from_user.full_name or message.from_user.username or user_id}")
    except Exception as e:
        logger.error(f"Error uploading downloaded file: {e}")
        if waiting_msg:
            try: waiting_msg.delete()
            except: pass
        try:
            os.remove(temp_path)
        except:
            pass
        return message.reply_text("❌ Failed to upload the downloaded file to storage.")

    # Generate file link and save history
    try:
        file_id = generate_file_id(user_id, sent.message_id)
        bot_username = context.bot.username
        link = f"https://t.me/{bot_username}?start={file_id}"
        save_history(user_id, filename, link)
    except Exception as e:
        logger.error(f"Error generating link or saving history for URL upload: {e}")
        link = "error_generating_link"

    # remove waiting message
    if waiting_msg:
        try: waiting_msg.delete()
        except: pass

    # reply with full message
    try:
        message.reply_text(
            f"🎉 *URL File Uploaded Successfully!*\n\n"
            f"📂 *File:* `{filename}`\n"
            f"🔗 *Direct Link:* `{link}`\n\n"
            f"🌟 *Powered By* @BhramsBots",
            parse_mode="MARKDOWN",
            disable_web_page_preview=True
        )
    except Exception:
        # fallback simple reply
        message.reply_text(f"URL uploaded: {filename}\nLink: {link}")

    # cleanup temp file
    try:
        os.remove(temp_path)
    except:
        pass

# ---------- /start Handler ----------
def start(update: Update, context: CallbackContext) -> None:
    # Block banned users
    if is_banned(update.effective_user.id):
        return update.message.reply_text("⛔ You are banned from using this bot because of sending inappropriate content.")

    user_id = update.effective_user.id
    save_user(user_id)
    args = context.args  # deep link

    # Deep-link file retrieval
    if args:
        try:
            file_id = args[0]
            parts = file_id.split("_")
            if len(parts) == 3:
                _, original_user, message_id = parts
                original_user = int(original_user)
                message_id = int(message_id)

                bot.copy_message(
                    chat_id=user_id,
                    from_chat_id=GROUP_CHAT_ID,
                    message_id=message_id
                )

                update.message.reply_text(
                    "📥 *Here’s your file!*\n"
                    "⚠️ Do not share this link.",
                    parse_mode="MARKDOWN"
                )
                return
            else:
                return update.message.reply_text("⚠️ Invalid or expired link.")
        except Exception as e:
            logger.error(f"Error retrieving file: {e}")
            return update.message.reply_text("❌ File not found or may have been removed.")

    # Welcome message
    first = update.effective_user.first_name
    username = update.effective_user.username
    raw = first or username or "User"
    short_name = raw.strip().split()[0].capitalize()
    if len(short_name) > 20:
        short_name = short_name[:19] + "…"

    update.message.reply_text(
        f"👋 Hi <b>{short_name}</b>!\n\n"
        "✨ <b>Welcome to Free Storage Bot!</b> ✨\n\n"
        "Send me a file 📁 to store in our database and also you can get a download link 🔗.\n"
        "Send a *direct file URL* (ends with .pdf/.mp4/.jpg etc.) to upload from the web.\n\n"
        "📌 <b>Commands:</b>\n"
        "• /start\n"
        "• /help\n"
        "• /history\n\n"
        "⚠️ <b>Notice:</b> Do not upload illegal or adult content, otherwise you’ll be <b>BANNED</b>.",
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

# ---------- Ban / Unban ----------
def ban(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        return update.message.reply_text("⛔ Admin only.")

    if not context.args:
        return update.message.reply_text("Usage: /ban <user_id>")

    target = context.args[0]
    save_banned(target)

    update.message.reply_text(f"🚫 User {target} has been banned.")

def unban(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        return update.message.reply_text("⛔ Admin only.")

    if not context.args:
        return update.message.reply_text("Usage: /unban <user_id>")

    target = context.args[0]
    banned = load_banned()

    if target in banned:
        banned.remove(target)
        with open(BANNED_FILE, "w") as f:
            f.write("\n".join(banned))

        update.message.reply_text(f"✅ User {target} is unbanned.")
    else:
        update.message.reply_text("User was not banned.")

# ---------- /history ----------
def history(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    records = get_user_history(user_id)

    if not records:
        return update.message.reply_text("📭 You have no upload history yet!")

    response = "📜 *Your Recent Uploads:*\n\n"
    count = 1

    for record in records:
        uid, fname, link = record.split("|")
        response += f"{count}️⃣ *{fname}*\n🔗 `{link}`\n\n"
        count += 1

    update.message.reply_text(response, parse_mode="MARKDOWN", disable_web_page_preview=True)

# ---------- /help ----------
def help_command(update: Update, context: CallbackContext) -> None:
    bot_username = context.bot.username
    update.message.reply_text(
        "📌 *How to Use this Bot:*\n\n"
        "1. Send any file (document, photo, video, audio).\n"
        "2. Send a direct file URL (link that ends with .pdf/.mp4/.jpg etc.).\n"
        "3. Use /history to see last 5 uploads.\n\n"
        f"Retrieve files using deep-links: https://t.me/{bot_username}?start=<FileID>",
        parse_mode="MARKDOWN"
    )

# ---------- File Upload Handler ----------
def handle_file(update: Update, context: CallbackContext) -> None:
    global file_count
    message = update.message

    # If text and a direct URL, handle via handle_url (this will only run for direct-file links)
    if message.text and (message.text.startswith("http://") or message.text.startswith("https://")):
        # Let handle_url decide if it's downloadable (it checks extension)
        return handle_url(update, context)

    user_id = message.from_user.id

    # Banned users cannot upload
    if is_banned(user_id):
        return message.reply_text("⛔ You are banned and cannot upload files.")

    save_user(user_id)

    user_name = message.from_user.full_name or message.from_user.username or "Unknown User"

    try:
        # 1️⃣ Identity message to your group
        bot.send_message(
            chat_id=GROUP_CHAT_ID,
            text=(
                "📨 <b>New Upload Received</b>\n"
                f"👤 <b>User:</b> {user_name}\n"
                f"🆔 <b>User ID:</b> <code>{user_id}</code>\n\n"
                "⬇️ File below:"
            ),
            parse_mode="HTML"
        )

        # 2️⃣ Copy the actual file to your group
        copied_msg = bot.copy_message(
            chat_id=GROUP_CHAT_ID,
            from_chat_id=message.chat_id,
            message_id=message.message_id
        )

        # Generate file ID for retrieval
        file_id = generate_file_id(user_id, copied_msg.message_id)
        file_count += 1
        bot_username = context.bot.username
        link = f"https://t.me/{bot_username}?start={file_id}"

        # -------- Detailed message to user --------
        file_name = "Unknown"
        file_size = "Unknown"
        file_type = "Media"

        if message.document:
            file_name = message.document.file_name
            file_size = f"{round(message.document.file_size / (1024 * 1024), 2)} MB"
            file_type = "Document"
        elif message.photo:
            file_name = "Photo"
            file_type = "Photo"
        elif message.video:
            file_name = "Video"
            file_size = f"{round(message.video.file_size / (1024 * 1024), 2)} MB"
            file_type = "Video"
        elif message.audio:
            file_name = message.audio.file_name or "Audio"
            file_size = f"{round(message.audio.file_size / (1024 * 1024), 2)} MB"
            file_type = "Audio"

        # Save history (so /history will show the new upload)
        save_history(user_id, file_name, link)

        message.reply_text(
            f"🎉 *Hurray !! Your File has been Uploaded to Our Server*\n\n"
            f"📂 *File Name:* `{file_name}`\n"
            f"📊 *File Size:* {file_size}\n\n"
            f"🔗 *Here is Your Direct Link:*\n"
            f"`{link}`\n\n"
            f"🌟 *Powered By* @BhramsBots\n\n"
            f"📁 *Type:* {file_type}\n"
            f"🚸 *Note:* Your Link is Stored Safely Until Admins Action !",
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
dispatcher.add_handler(CommandHandler("ban", ban))
dispatcher.add_handler(CommandHandler("unban", unban))
dispatcher.add_handler(CommandHandler("help", help_command))
dispatcher.add_handler(CommandHandler("history", history))
# Message handlers — text URL check first, then all other media/messages
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_url))
dispatcher.add_handler(MessageHandler(Filters.all & ~Filters.command, handle_file))

# ---------- Main ----------
if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=PORT)
