# bot.py (Render-ready, optimized for Render)
import os
import logging
import requests
import tempfile
import time
from flask import Flask, request
from telegram import Update, Bot
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters, CallbackContext

# ---------- Config ----------
BOT_TOKEN = os.getenv("BOT_TOKEN")
# FORCE_CHANNELS = [
#     "@earningstoreofficialsss",
#     "@Tashandenix"
# ]

FORCE_CHANNELS = [
    "@earningstoreofficialsss",   # public
    "@BhramsBots1",
    "@Earning_Flash",
    # -1002063639089,
    # -1001585393657,
    # -1002067012336
    # -1001484298206,
    # "@Tashandenix",               # public (if exists)
    -1001707828848                # private (Denix Predictions 🚀)
]


GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "-1002909394259"))
ADMIN_ID = int(os.getenv("ADMIN_ID", "1317903617"))
USERS_FILE = os.getenv("USERS_FILE", "users.txt")
BANNED_FILE = "banned.txt"
HISTORY_FILE = "history.txt"

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN env variable missing!")

bot = Bot(BOT_TOKEN)

# ---------- Logging ----------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

file_count = 0
def help_command(update, context):
    bot_username = context.bot.username
    update.message.reply_text(
        "📌 *How to use Free Storage Bot*\n\n"
        "📁 Send any file to upload\n"
        "🌐 Send image URL (jpg/png/webp under 10MB)\n"
        "🕒 /history – View last 5 uploads\n\n"
        f"🔗 Access files:\nhttps://t.me/{bot_username}?start=<FileID>\n\n"
        "⚠️ Adult or illegal content = permanent ban",
        parse_mode="MARKDOWN"
    )
# def is_user_joined(user_id, context):
#     for channel in FORCE_CHANNELS:
#         try:
#             member = context.bot.get_chat_member(channel, user_id)
#             if member.status not in ["member", "administrator", "creator"]:
#                 return False
#         except:
#             return False
#     return True
def is_user_joined(user_id, context):
    for channel in FORCE_CHANNELS:
        try:
            member = context.bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in ["left", "kicked"]:
                return False
        except Exception as e:
            logger.error(f"Join check failed for {channel}: {e}")
            return False
    return True


def force_join_message(update):
    keyboard = [
    # [InlineKeyboardButton("📢 Join Bonus channel ", url="https://t.me/+nndBvmQBvLthZGFl")],
    [InlineKeyboardButton("📢 Join Channel 1", url="https://telegram.me/+AyLDRuPW1TliNzA9")],
    # [InlineKeyboardButton("📢 Join Channel 1", url="https://telegram.me/Earning_Flash")],
    
    [InlineKeyboardButton("📢 Join Channel 2", url="https://telegram.me/earningstoreofficialsss")],
    [InlineKeyboardButton("📢 Join Channel 3", url="https://telegram.me/BhramsBots1")],
    [InlineKeyboardButton("📢 Join Private ", url="https://telegram.me/+FlL_2rBBoQg1NmRl")],
    # [InlineKeyboardButton("📢 Join Private 4", url="https://telegram.me/+-mexi0ilD582N2Fl")],
    [InlineKeyboardButton("✅ I Joined", callback_data="verify_join")]
]

    # keyboard = [
    #     [InlineKeyboardButton("📢 Join Channel 1", url="https://t.me/earningstoreofficialsss")],
    #     [InlineKeyboardButton("📢 Join Channel 2", url="https://t.me/Tashandenix")],
    #     [InlineKeyboardButton("✅ I Joined", callback_data="verify_join")]
    # ]
#     keyboard = [
#     [InlineKeyboardButton("📢 Join Channel", url="https://t.me/earningstoreofficialsss")],
#     [InlineKeyboardButton("✅ I Joined", callback_data="verify_join")]
# ]
    

    update.message.reply_text(
        "🚫 *Access Denied*\n\n"
        # "You must join *both channels* to use this bot.\n\n"
        "You must join the *All Channels* to use this bot.\n\n"
        "After joining, click *I Joined*.",
        parse_mode="MARKDOWN",
        reply_markup=InlineKeyboardMarkup(keyboard),
        disable_web_page_preview=True
    )




# ---------- Helper ----------
def generate_file_id(user_id, message_id):
    return f"{int(time.time())}_{user_id}_{message_id}"

def save_user(uid):
    uid = str(uid)
    users = set()

    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            users = set(x.strip() for x in f if x.strip())

    if uid not in users:
        with open(USERS_FILE, "a") as f:
            f.write(uid + "\n")

def load_banned():
    if not os.path.exists(BANNED_FILE):
        return set()
    return set(x.strip() for x in open(BANNED_FILE, "r") if x.strip())

def save_banned(uid):
    banned = load_banned()
    if str(uid) not in banned:
        with open(BANNED_FILE, "a") as f:
            f.write(f"{uid}\n")

def is_banned(uid):
    return str(uid) in load_banned()

# ---------- HISTORY ----------
def save_history(uid, filename, link):
    with open(HISTORY_FILE, "a") as f:
        f.write(f"{uid}|{filename}|{link}\n")

def get_user_history(uid, limit=5):
    if not os.path.exists(HISTORY_FILE):
        return []
    with open(HISTORY_FILE, "r") as f:
        lines = [x.strip() for x in f if x.strip()]
    records = [x for x in lines if x.startswith(str(uid) + "|")]
    return records[-limit:]

# ---------- STATS ----------
def stats(update, context):
    if update.effective_user.id != ADMIN_ID:
        return update.message.reply_text("⛔ Admin only.")

    total_users = 0
    banned_users = 0

    if os.path.exists(USERS_FILE):
        with open(USERS_FILE) as f:
            total_users = len([x for x in f if x.strip()])

    if os.path.exists(BANNED_FILE):
        with open(BANNED_FILE) as f:
            banned_users = len([x for x in f if x.strip()])

    active_users = total_users - banned_users

    update.message.reply_text(
        f"📊 *Bot Statistics*\n\n"
        f"👥 Total Users : `{total_users}`\n"
        f"✅ Active Users : `{active_users}`\n"
        f"🚫 Banned Users : `{banned_users}`",
        parse_mode="MARKDOWN"
    )
# ---------- URL VALIDATION ----------
VALID_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp")

def is_direct_file_url(url):
    url = url.lower().split("?")[0].split("#")[0]
    return any(url.endswith(ext) for ext in VALID_EXTENSIONS)

# ---------- DOWNLOAD IMAGE (<10MB) ----------
def download_file_from_url(url, timeout=30):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, stream=True, timeout=timeout, headers=headers)

        if r.status_code != 200:
            return None, None

        filename = url.split("/")[-1].split("?")[0]

        tmp = tempfile.NamedTemporaryFile(delete=False, prefix="img_", suffix=filename)
        tmp_path = tmp.name
        tmp.close()

        downloaded = 0
        max_size = 10 * 1024 * 1024  # 10MB

        with open(tmp_path, "wb") as f:
            for chunk in r.iter_content(8192):
                if chunk:
                    downloaded += len(chunk)

                    if downloaded > max_size:
                        f.close()
                        os.remove(tmp_path)
                        return None, None

                    f.write(chunk)

        return tmp_path, filename

    except Exception as e:
        logger.error(f"Download error: {e}")
        return None, None

# ---------- URL Handler ----------
def handle_url(update, context):
    msg = update.message
    url = msg.text.strip()

    if not (url.startswith("http://") or url.startswith("https://")):
        return

    if not is_direct_file_url(url):
        return msg.reply_text(
            "⚠️ Only small *image links* are supported.\n\n"
            "Allowed: JPG, PNG, GIF, WEBP (<10MB)\n"
            "Videos, PDFs, ZIPs, APKs ❌ Not supported on this host."
        )

    uid = msg.from_user.id
    if is_banned(uid):
        return msg.reply_text("⛔ You are banned.")

    waiting = msg.reply_text("⬇️ Downloading image...")

    temp_path, filename = download_file_from_url(url)
    if not temp_path:
        try: waiting.delete()
        except: pass
        return msg.reply_text("❌ Failed to download image. File too large or server blocked.")

    try:
        with open(temp_path, "rb") as f:
            sent = bot.send_document(
                chat_id=GROUP_CHAT_ID,
                document=f,
                caption=f"Uploaded via URL by {msg.from_user.full_name}"
            )
    except:
        return msg.reply_text("❌ Failed to upload image.")

    file_id = generate_file_id(uid, sent.message_id)
    link = f"https://t.me/{context.bot.username}?start={file_id}"

    save_history(uid, filename, link)

    try: waiting.delete()
    except: pass


# ---------- START ----------
def start(update, context):
    if not is_user_joined(update.effective_user.id, context):
        return force_join_message(update)
    user = update.effective_user
    uid = user.id

    if is_banned(uid):
        return update.message.reply_text("⛔ You are banned.")

    save_user(uid)

    # deep link
    args = context.args
    if args:
        try:
            ts, original_user, mid = args[0].split("_")
            bot.copy_message(uid, GROUP_CHAT_ID, int(mid))
            return update.message.reply_text("📥 Here is your file!")
        except:
            return update.message.reply_text("❌ Invalid link.")

    name = user.first_name or user.username or "User"
    name = name.split()[0].capitalize()

    update.message.reply_text(
        f"👋 Hi <b>{name}</b>!\n\n"
        "✨ Welcome to Free Storage Bot ✨\n\n"
        "📁 Send any file to upload\n"
        "🌐 Send an image URL (jpg/png/webp)\n"
        "🕒 Use /history to view previous files\n\n"
        "⚠️ Adult or illegal content = Ban",
        parse_mode="HTML"
    )

# ---------- ANNOUNCE ----------
# ---------- ANNOUNCE ----------
def announce(update, context):
    if update.effective_user.id != ADMIN_ID:
        return update.message.reply_text("⛔ Admin only.")

    if not context.args:
        return update.message.reply_text("Usage: /announce message")

    message = " ".join(context.args)

    if not os.path.exists(USERS_FILE):
        return update.message.reply_text("No users found.")

    with open(USERS_FILE) as f:
        users = list(set(x.strip() for x in f if x.strip()))

    sent = 0
    failed = 0

    for uid in users:
        try:
            bot.send_message(uid, message)
            sent += 1
            time.sleep(0.03)
        except:
            failed += 1

    update.message.reply_text(
        f"📢 Announcement Report\n\n"
        f"📨 Sent : {sent} users\n"
        f"❌ Failed : {failed} users"
    )
# ---------- Ban / Unban ----------
def ban(update, context):
    if update.effective_user.id != ADMIN_ID:
        return update.message.reply_text("⛔ Admin only.")
    if not context.args:
        return update.message.reply_text("Usage: /ban id")

    save_banned(context.args[0])
    update.message.reply_text("User banned.")

def unban(update, context):
    if update.effective_user.id != ADMIN_ID:
        return update.message.reply_text("⛔ Admin only.")
    if not context.args:
        return update.message.reply_text("Usage: /unban id")

    uid = context.args[0]
    banned = load_banned()

    if uid in banned:
        banned.remove(uid)
        with open(BANNED_FILE, "w") as f:
            f.write("\n".join(banned))
        return update.message.reply_text("User unbanned.")
    update.message.reply_text("User was not banned.")

# ---------- HISTORY ----------
def history(update, context):
    uid = update.effective_user.id
    records = get_user_history(uid)

    if not records:
        return update.message.reply_text("📭 No history found.")

    txt = "📜 *Your Upload History:*\n\n"
    n = 1
    for r in records:
        _, fname, link = r.split("|")
        txt += f"{n}️⃣ *{fname}*\n🔗 `{link}`\n\n"
        n += 1

    update.message.reply_text(txt, parse_mode="MARKDOWN")

# ---------- FILE UPLOAD ----------
def handle_file(update, context):
    msg = update.message
    uid = msg.from_user.id

    if not is_user_joined(uid, context):
        return force_join_message(update)

    # if it's a URL, let handle_url handle it
    # if msg.text and (msg.text.startswith("http://") or msg.text.startswith("https://")):
    #     return handle_url(update, context)

    if is_banned(uid):
        return msg.reply_text("⛔ You are banned.")

    save_user(uid)

    user_name = msg.from_user.full_name or msg.from_user.username or "Unknown User"

    bot.send_message(
        GROUP_CHAT_ID,
        f"📨 <b>New Upload</b>\n👤 {user_name}\n🆔 <code>{uid}</code>",
        parse_mode="HTML"
    )

    sent = bot.copy_message(GROUP_CHAT_ID, msg.chat_id, msg.message_id)

    file_id = generate_file_id(uid, sent.message_id)
    link = f"https://t.me/{context.bot.username}?start={file_id}"

    save_history(uid, "File", link)

    file_name = msg.document.file_name if msg.document else "Unknown File"
    file_size = msg.document.file_size if msg.document else 0
    file_size_mb = round(file_size / (1024 * 1024), 2)

    msg.reply_text(
        f"🎉 *Hurray !! Your File has been Uploaded to Our Server*\n\n"
        f"📂 *File Name:* `{file_name}`\n"
        f"📊 *File Size:* `{file_size_mb} MB`\n\n"
        f"🔗 *Here is Your Direct Link:*\n"
        f"`{link}`\n\n"
        f"🌟 *Powered By* @BhramsBots\n\n"
        f"📁 *Type:* Document\n"
        f"🚸 *Note:* Your Link is Stored Safely Until Admins Action !",
        parse_mode="MARKDOWN"
    )

def verify_join(update, context):
    query = update.callback_query
    user_id = query.from_user.id

    if is_user_joined(user_id, context):
        query.answer("✅ Verified!")
        query.message.edit_text(
            "✅ *Verification successful!*\n\nYou can now use the bot.",
            parse_mode="MARKDOWN"
        )
    else:
        query.answer("❌ You have not joined all channels!", show_alert=True)

# ---------- Flask ----------
app = Flask(__name__)

@app.route("/")
def index():
    return "Bot running", 200

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(), bot)
    dispatcher.process_update(update)
    return "ok", 200

# ---------- Dispatcher ----------
dispatcher = Dispatcher(bot, None, workers=4)
dispatcher.add_handler(CallbackQueryHandler(verify_join, pattern="verify_join"))
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("help", help_command))
dispatcher.add_handler(CommandHandler("history", history))
dispatcher.add_handler(CommandHandler("ban", ban))
dispatcher.add_handler(CommandHandler("unban", unban))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_url))
dispatcher.add_handler(MessageHandler(Filters.all & ~Filters.command, handle_file))
dispatcher.add_handler(CommandHandler("announce", announce))
dispatcher.add_handler(CommandHandler("stats", stats))

# ---------- Main ----------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
