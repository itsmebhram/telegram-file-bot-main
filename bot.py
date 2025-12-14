# bot.py (Render-ready, corrected & stable)

import threading
import os
import logging
import requests
import tempfile
import time
from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters

# ---------- Config ----------
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "-1002909394259"))
ADMIN_ID = int(os.getenv("ADMIN_ID", "1317903617"))
USERS_FILE = "users.txt"
BANNED_FILE = "banned.txt"
HISTORY_FILE = "history.txt"

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN env variable missing!")

bot = Bot(BOT_TOKEN)

# ---------- Logging ----------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------- Helpers ----------
def generate_file_id(uid, mid):
    return f"{int(time.time())}_{uid}_{mid}"

def save_user(uid):
    if not os.path.exists(USERS_FILE):
        open(USERS_FILE, "w").close()
    with open(USERS_FILE, "r") as f:
        if str(uid) not in f.read():
            with open(USERS_FILE, "a") as fw:
                fw.write(f"{uid}\n")

def load_banned():
    if not os.path.exists(BANNED_FILE):
        return set()
    return set(x.strip() for x in open(BANNED_FILE))

def is_banned(uid):
    return str(uid) in load_banned()

def save_history(uid, fname, link):
    with open(HISTORY_FILE, "a") as f:
        f.write(f"{uid}|{fname}|{link}\n")

def get_user_history(uid, limit=5):
    if not os.path.exists(HISTORY_FILE):
        return []
    with open(HISTORY_FILE) as f:
        rows = [x.strip() for x in f if x.startswith(str(uid))]
    return rows[-limit:]

# ---------- URL ----------
VALID_EXT = (".jpg", ".jpeg", ".png", ".gif", ".webp")

def is_direct_image(url):
    url = url.lower().split("?")[0]
    return any(url.endswith(e) for e in VALID_EXT)

def download_image(url):
    r = requests.get(url, stream=True, timeout=20)
    if r.status_code != 200:
        return None, None

    fname = url.split("/")[-1]
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=fname)
    size = 0

    for c in r.iter_content(8192):
        size += len(c)
        if size > 10 * 1024 * 1024:
            tmp.close()
            os.remove(tmp.name)
            return None, None
        tmp.write(c)

    tmp.close()
    return tmp.name, fname

# ---------- Handlers ----------
def start(update, context):
    uid = update.effective_user.id
    save_user(uid)

    if context.args:
        try:
            _, _, mid = context.args[0].split("_")
            bot.copy_message(uid, GROUP_CHAT_ID, int(mid))
            return update.message.reply_text("📥 Here is your file!")
        except:
            return update.message.reply_text("❌ Invalid link.")

    update.message.reply_text(
        "👋 Welcome!\n\n"
        "📁 Send files\n"
        "🌐 Send image URL\n"
        "🕒 /history – last 5 files"
    )

def help_command(update, context):
    update.message.reply_text(
        "📌 Commands\n\n"
        "/start – Start bot\n"
        "/history – Last 5 uploads\n"
        "/announce – Admin only\n\n"
        "Send images (JPG/PNG/WEBP <10MB)"
    )

def history(update, context):
    rows = get_user_history(update.effective_user.id)
    if not rows:
        return update.message.reply_text("📭 No history")

    msg = "📜 Your last uploads:\n\n"
    for i, r in enumerate(rows, 1):
        _, f, l = r.split("|")
        msg += f"{i}. {f}\n{l}\n\n"
    update.message.reply_text(msg)

def handle_url(update, context):
    text = update.message.text
    if not text.startswith("http"):
        return

    if not is_direct_image(text):
        return update.message.reply_text("❌ Only direct image links allowed")

    wait = update.message.reply_text("⬇️ Downloading...")
    path, fname = download_image(text)
    if not path:
        return update.message.reply_text("❌ Download failed")

    with open(path, "rb") as f:
        sent = bot.send_document(GROUP_CHAT_ID, f)

    link = f"https://t.me/{context.bot.username}?start={generate_file_id(update.effective_user.id, sent.message_id)}"
    save_history(update.effective_user.id, fname, link)

    wait.delete()
    update.message.reply_text(f"✅ Uploaded\n{link}")
    os.remove(path)

# ---------- Broadcast ----------
def announce(update, context):
    if update.effective_user.id != ADMIN_ID:
        return update.message.reply_text("Admin only")

    if not context.args:
        return update.message.reply_text("Usage: /announce text")

    update.message.reply_text("📢 Broadcast started…")
    threading.Thread(target=run_broadcast, args=(" ".join(context.args),)).start()

def run_broadcast(text):
    sent = failed = 0
    for uid in open(USERS_FILE):
        try:
            bot.send_message(int(uid.strip()), text)
            sent += 1
            time.sleep(0.03)
        except:
            failed += 1

    bot.send_message(
        ADMIN_ID,
        f"✅ Broadcast done\nSent: {sent}\nFailed: {failed}"
    )

# ---------- Flask ----------
app = Flask(__name__)

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(), bot)
    dispatcher.process_update(update)
    return "ok"

# ---------- Dispatcher ----------
dispatcher = Dispatcher(bot, None, workers=4)
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("help", help_command))
dispatcher.add_handler(CommandHandler("history", history))
dispatcher.add_handler(CommandHandler("announce", announce))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_url))

# ---------- Run ----------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
