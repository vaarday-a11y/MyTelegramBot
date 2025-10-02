# bot.py
import os
import re
import uuid
import shutil
import logging
import tempfile
import requests
from pathlib import Path
from threading import Thread
from flask import Flask, send_from_directory

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackQueryHandler, Filters, CallbackContext

import yt_dlp
import instaloader

# ----------------------------
# Config / Logging
# ----------------------------
logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Env vars
TOKEN = os.environ.get("TELEGRAM_TOKEN") or os.environ.get("BOT_TOKEN") or os.environ.get("TOKEN")
if not TOKEN:
    logger.error("Missing TELEGRAM_TOKEN environment variable")
    raise SystemExit("Missing TELEGRAM_TOKEN environment variable")

COOKIES_TEXT = os.environ.get("COOKIES_TXT")        # cookie matni (agar paste qilingan bo'lsa)
COOKIE_FILE_PATH = os.environ.get("COOKIE_FILE_PATH")  # yoki repo ichidagi cookies fayl nomi

# Default Telegram safe limit (1.9GB). O'zgartirish uchun env qo'yishingiz mumkin.
MAX_TELEGRAM_BYTES = int(os.environ.get("MAX_TELEGRAM_BYTES", 1900 * 1024 * 1024))

# RAILWAY_URL (sizning deployed app URLingiz, masalan: my-bot.up.railway.app)
RAILWAY_URL = os.environ.get("RAILWAY_URL", "").strip().rstrip("/")

# directories
DOWNLOADS_DIR = "downloads"
STATIC_DIR = "static"
os.makedirs(DOWNLOADS_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

# In-memory store for long URLs (callback_data limit avoidance)
URL_STORE = {}

# ----------------------------
# Flask for static serving (fallback when transfer.sh fails)
# ----------------------------
app = Flask(__name__)

@app.route("/downloads/<path:filename>")
def download_file(filename):
    return send_from_directory(DOWNLOADS_DIR, filename, as_attachment=True)

def run_flask():
    # Use port 8080 (Railway expects this or any allowed port)
    app.run(host="0.0.0.0", port=8080)

# Start Flask in background thread (safe to call; if Railway uses Docker it will serve)
Thread(target=run_flask, daemon=True).start()

# ----------------------------
# Helpers
# ----------------------------
def sizeof_fmt(num, suffix="B"):
    for unit in ["", "K", "M", "G", "T"]:
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Y{suffix}"

def find_media_files(root_dir):
    exts = {".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mkv", ".mov", ".webm", ".mp3", ".m4a", ".aac"}
    files = []
    for p in Path(root_dir).rglob("*"):
        if p.is_file() and p.suffix.lower() in exts:
            files.append(str(p))
    files.sort(key=lambda x: -Path(x).stat().st_size)
    return files

def download_binary(url, path):
    try:
        r = requests.get(url, stream=True, timeout=30)
        r.raise_for_status()
        with open(path, "wb") as f:
            for chunk in r.iter_content(1024 * 32):
                f.write(chunk)
        return True
    except Exception as e:
        logger.exception("download_binary error: %s", e)
        return False

def upload_to_transfersh(file_path):
    """
    Upload to transfer.sh (simple fallback). Returns public link or None.
    """
    try:
        filename = Path(file_path).name
        url = f"https://transfer.sh/{filename}"
        with open(file_path, "rb") as f:
            # transfer.sh accepts PUT of raw file
            resp = requests.put(url, data=f, timeout=180)
        if resp.status_code in (200, 201):
            link = resp.text.strip()
            logger.info("Uploaded to transfer.sh: %s", link)
            return link
        else:
            logger.warning("transfer.sh upload failed: %s %s", resp.status_code, resp.text[:200])
            return None
    except Exception as e:
        logger.exception("transfer.sh upload exception: %s", e)
        return None

# ----------------------------
# Core fetch logic (unchanged behavior + robust)
# ----------------------------
def fetch_media(url: str, choice: str):
    """
    Returns tuple: (file_path, media_type) on success,
                   (None, error_message) on failure.
    """
    tmpdir = tempfile.mkdtemp(prefix="botdl_")
    cookiefile = None

    # create cookie file from COOKIES_TEXT if provided
    if COOKIES_TEXT:
        try:
            cookiefile = os.path.join(tmpdir, "cookies.txt")
            with open(cookiefile, "w", encoding="utf-8") as cf:
                cf.write(COOKIES_TEXT)
        except Exception:
            cookiefile = None

    # or use cookie file from repo if specified
    if not cookiefile and COOKIE_FILE_PATH and os.path.exists(COOKIE_FILE_PATH):
        cookiefile = COOKIE_FILE_PATH

    outtmpl = os.path.join(tmpdir, "%(id)s.%(ext)s")
    ydl_opts = {
        "outtmpl": outtmpl,
        "noplaylist": True,
        "ignoreerrors": True,
        "no_warnings": True,
        "restrictfilenames": True,
    }
    if cookiefile:
        ydl_opts["cookiefile"] = cookiefile

    if choice == "video":
        ydl_opts["format"] = "bestvideo+bestaudio/best"
        ydl_opts["merge_output_format"] = "mp4"
    elif choice == "audio":
        ydl_opts["format"] = "bestaudio/best"
        ydl_opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]
    elif choice == "image":
        ydl_opts["format"] = "best"
    else:
        shutil.rmtree(tmpdir, ignore_errors=True)
        return None, f"Not supported choice: {choice}"

    info = None
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=(choice != "image"))
            logger.info("yt-dlp info keys: %s", list(info.keys()) if isinstance(info, dict) else "no-info")
    except Exception as e:
        logger.exception("yt-dlp error: %s", e)
        info = None

    downloaded_files = find_media_files(tmpdir)

    # if image requested or nothing downloaded, try to get thumbnails or media URLs from info
    if (choice == "image" or not downloaded_files) and info:
        try:
            candidates = []
            if isinstance(info, dict):
                if "entries" in info and info["entries"]:
                    for e in info["entries"]:
                        if isinstance(e, dict):
                            if e.get("url") and re.search(r"\.(jpg|jpeg|png|webp)$", e.get("url"), re.I):
                                candidates.append(e.get("url"))
                            if e.get("thumbnail"):
                                candidates.append(e.get("thumbnail"))
                if info.get("url") and re.search(r"\.(jpg|jpeg|png|webp)$", info.get("url"), re.I):
                    candidates.append(info.get("url"))
                if info.get("thumbnail"):
                    candidates.append(info.get("thumbnail"))
                if info.get("thumbnails"):
                    for t in info.get("thumbnails"):
                        if isinstance(t, dict) and t.get("url"):
                            candidates.append(t.get("url"))
            candidates = [c for i, c in enumerate(candidates) if c and c not in candidates[:i]]
            for idx, img_url in enumerate(candidates):
                ext = Path(img_url).suffix or ".jpg"
                path = os.path.join(tmpdir, f"img_{idx}{ext}")
                if download_binary(img_url, path):
                    downloaded_files.append(path)
        except Exception as e:
            logger.exception("image-from-info error: %s", e)

    # instaloader fallback for Instagram if still nothing
    if not downloaded_files and "instagram.com" in url:
        try:
            L = instaloader.Instaloader(dirname_pattern=tmpdir, download_videos=True, save_metadata=False, post_metadata_txt_pattern=None)
            m = re.search(r"(?:/p/|/reel/|/tv/)([^/?#&]+)", url)
            shortcode = m.group(1) if m else None
            if shortcode:
                post = instaloader.Post.from_shortcode(L.context, shortcode)
                L.download_post(post, target=shortcode)
                downloaded_files = find_media_files(tmpdir)
        except Exception as e:
            logger.exception("instaloader fallback error: %s", e)

    if downloaded_files:
        chosen = max(downloaded_files, key=lambda p: Path(p).stat().st_size)
        ext = Path(chosen).suffix.lower()
        if ext in [".jpg", ".jpeg", ".png", ".webp"]:
            mtype = "photo"
        elif ext in [".mp3", ".m4a", ".aac", ".ogg"]:
            mtype = "audio"
        else:
            mtype = "video"

        size = Path(chosen).stat().st_size
        # keep file in tmpdir for caller to handle; we will not delete tmpdir here
        return chosen, mtype

    shutil.rmtree(tmpdir, ignore_errors=True)
    return None, "Media not found or private. If private, set COOKIES_TXT or COOKIE_FILE_PATH."

# ----------------------------
# Telegram handlers
# ----------------------------
def start_handler(update: Update, context: CallbackContext):
    update.message.reply_text("👋 Salom! Menga YouTube, TikTok yoki Instagram link yuboring — keyin Video/Audio/Rasm tanlaysiz.")

def handle_link(update: Update, context: CallbackContext):
    text = update.message.text or ""
    urls = re.findall(r'(https?://\S+|www\.\S+)', text)
    if not urls:
        update.message.reply_text("❌ Iltimos haqiqiy havola yuboring.")
        return
    url = urls[0].strip()
    uid = uuid.uuid4().hex
    URL_STORE[uid] = url
    keyboard = [
        [
            InlineKeyboardButton("🎥 Video", callback_data=f"video|{uid}"),
            InlineKeyboardButton("🎵 Audio", callback_data=f"audio|{uid}"),
            InlineKeyboardButton("🖼️ Rasm", callback_data=f"image|{uid}")
        ]
    ]
    update.message.reply_text("Qaysi formatda yuklab olmoqchisiz?", reply_markup=InlineKeyboardMarkup(keyboard))

def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    if not query:
        return
    query.answer()
    data = query.data or ""
    if "|" not in data:
        query.message.reply_text("❌ Noto'g'ri so'rov.")
        return
    choice, uid = data.split("|", 1)
    uid = uid.strip()
    if uid not in URL_STORE:
        query.message.reply_text("❌ Havola topilmadi yoki eskirgan. Iltimos, havolani qayta yuboring.")
        return
    url = URL_STORE.pop(uid)
    try:
        query.edit_message_text("⏳ Yuklanmoqda... Iltimos kuting.")
    except Exception:
        pass

    file_path, info = fetch_media(url, choice)
    if not file_path:
        try:
            query.message.reply_text(f"❌ Xatolik: {info}")
        except Exception:
            pass
        return

    try:
        size = Path(file_path).stat().st_size
        # If small enough, send directly
        if size <= MAX_TELEGRAM_BYTES:
            with open(file_path, "rb") as fh:
                if info == "photo":
                    query.message.reply_photo(photo=fh)
                elif info == "audio":
                    query.message.reply_audio(audio=fh)
                else:
                    query.message.reply_video(video=fh)
            query.message.reply_text(f"✅ Yuklab berildi ({sizeof_fmt(size)})")
        else:
            # try transfer.sh upload
            query.message.reply_text(f"⚠️ Fayl juda katta ({sizeof_fmt(size)}). Yuklanmoqda (transfer.sh)...")
            link = upload_to_transfersh(file_path)
            if link:
                query.message.reply_text(f"🔗 Fayl yuklandi: {link}")
            else:
                # fallback: move to downloads and provide railway link
                dst_name = os.path.basename(file_path)
                dst_path = os.path.join(DOWNLOADS_DIR, dst_name)
                shutil.move(file_path, dst_path)
                # Build link
                if RAILWAY_URL:
                    public_link = f"https://{RAILWAY_URL}/downloads/{dst_name}"
                    query.message.reply_text(f"🔗 Faylni bu yerdan yuklab oling:\n{public_link}")
                else:
                    query.message.reply_text("❌ transfer.sh'ga yuklash muvaffaqiyatsiz va RAILWAY_URL o'rnatilmagan. Iltimos admin bilan bog'laning.")
    except Exception as e:
        logger.exception("send error: %s", e)
        try:
            query.message.reply_text(f"❌ Faylni yuborishda xatolik: {e}")
        except Exception:
            pass
    finally:
        # cleanup tmpdir (fetch_media used tmpdir; attempt to remove it)
        try:
            base = Path(file_path).parents[0]
            shutil.rmtree(str(base), ignore_errors=True)
        except Exception:
            pass

# ----------------------------
# Main
# ----------------------------
def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start_handler))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_link))
    dp.add_handler(CallbackQueryHandler(button_handler))
    updater.start_polling()
    logger.info("Bot ishga tushdi, polling boshlandi.")
    updater.idle()

if __name__ == "__main__":
    main()
