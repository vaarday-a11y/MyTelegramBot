# bot.py
import os
import re
import uuid
import shutil
import logging
import tempfile
import requests
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackQueryHandler, Filters, CallbackContext

import yt_dlp
import instaloader

# ----------------------------
# Konfiguratsiya / Logging
# ----------------------------
logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# TOKENni Railway/GitHub secrets orqali oling (har qanday nom bilan: TELEGRAM_TOKEN yoki BOT_TOKEN)
TOKEN = os.environ.get("TELEGRAM_TOKEN") or os.environ.get("BOT_TOKEN") or os.environ.get("TOKEN")
if not TOKEN:
    logger.error("Telegram token topilmadi. Railway Variables ga TELEGRAM_TOKEN ni qo'shing.")
    raise SystemExit("Missing TELEGRAM_TOKEN environment variable")

# COOKIES_TXT: agar siz Railway Variables da cookies matnini to'g'ridan-to'g'ri qo'ysangiz (text)
# yoki COOKIE_FILE_PATH: agar repository ga cookies.txt faylini joylashtirgan bo'lsangiz (fayl nomi)
COOKIES_TEXT = os.environ.get("COOKIES_TXT")    # cookies faylining MATNI (agar qo'yilgan bo'lsa)
COOKIE_FILE_PATH = os.environ.get("COOKIE_FILE_PATH")  # misol: "cookies.txt" (agar fayl repo ichida bo'lsa)

# Telegram-ga yuborilishi ruxsat etilgan maksimal fayl hajmi (baytlarda)
MAX_TELEGRAM_BYTES = int(os.environ.get("MAX_TELEGRAM_MAX_BYTES", 50 * 1024 * 1024))

# Global in-memory store: uzun url'larni callback_data limitidan saqlash uchun
URL_STORE = {}

# ----------------------------
# Yordamchi funksiyalar
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
    # sort by size desc
    files.sort(key=lambda x: -Path(x).stat().st_size)
    return files

def download_binary(url, path):
    """Oddiy requests bilan fayl yuklab olish (thumbnail yoki image URL uchun)"""
    try:
        r = requests.get(url, stream=True, timeout=30)
        r.raise_for_status()
        with open(path, "wb") as f:
            for chunk in r.iter_content(1024 * 32):
                f.write(chunk)
        return True
    except Exception as e:
        logger.exception("download_binary xatosi: %s", e)
        return False

# ----------------------------
# Core yuklash funksiyasi
# ----------------------------
def fetch_media(url: str, choice: str):
    """
    url: link
    choice: "video" | "audio" | "image"
    Qaytaradi: (file_path, mime_type) yoki (None, error_message)
    """
    tmpdir = tempfile.mkdtemp(prefix="botdl_")
    cookiefile = None

    # 1) agar COOKIES_TEXT berilgan bo'lsa, vaqtinchalik cookie fayl yaratamiz
    if COOKIES_TEXT:
        try:
            cookiefile = os.path.join(tmpdir, "cookies.txt")
            with open(cookiefile, "w", encoding="utf-8") as cf:
                cf.write(COOKIES_TEXT)
        except Exception:
            cookiefile = None

    # 2) yoki repo ichidagi cookie fayl ko'rsatilgan bo'lsa (COOKIE_FILE_PATH)
    if not cookiefile and COOKIE_FILE_PATH and os.path.exists(COOKIE_FILE_PATH):
        cookiefile = COOKIE_FILE_PATH

    # ydl outtmpl papkaga yozilsin
    outtmpl = os.path.join(tmpdir, "%(id)s.%(ext)s")
    ydl_opts = {
        "outtmpl": outtmpl,
        "noplaylist": True,
        "ignoreerrors": True,
        "no_warnings": True,
        "restrictfilenames": True,
        # logger yoki progress qo'shishni xohlasangiz shu yerga qo'shing
    }

    # cookiefile qo'shamiz
    if cookiefile:
        ydl_opts["cookiefile"] = cookiefile

    # formatlar
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
        # biz avval video/streamni yuklashga urinmaymiz; ydl orqali info olishga urinib, image urlni olib requests bilan yuklaymiz
        ydl_opts["format"] = "best"
        # skip download default False — biz faqat thumbnails yoki media url ishlatamiz
    else:
        shutil.rmtree(tmpdir, ignore_errors=True)
        return None, f"Not supported choice: {choice}"

    downloaded_files = []

    # 1) birinchi urinish: yt-dlp bilan extract+download (video va audio uchun bu yetarli)
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=(choice != "image"))
            # info bo'lsa, ko'rib chiqamiz
            logger.info("yt-dlp info keys: %s", list(info.keys()) if isinstance(info, dict) else "no-info")
            # agar download=True bo'lsa, fayl(tmpdir)ga yozilgan bo'ladi
    except Exception as e:
        logger.exception("yt-dlp extract yoki download xatosi: %s", e)
        info = None

    # 2) topilgan fayllarni olamiz
    downloaded_files = find_media_files(tmpdir)

    # 3) agar image tanlangan bo'lsa yoki fayl topilmagan bo'lsa — info orqali image urlni qidirish
    if (choice == "image" or not downloaded_files) and info:
        # info turli shaklda bo'lishi mumkin
        try:
            # Reels / Postlarda thumbnail yoki url maydonlari bo'lishi mumkin
            candidates = []
            if isinstance(info, dict):
                # entries — carousel
                if "entries" in info and info["entries"]:
                    for e in info["entries"]:
                        # e may have 'thumbnail' or 'url'
                        if isinstance(e, dict):
                            if e.get("url") and re.search(r"\.(jpg|jpeg|png|webp)$", e.get("url"), re.I):
                                candidates.append(e.get("url"))
                            if e.get("thumbnail"):
                                candidates.append(e.get("thumbnail"))
                # for single post
                if info.get("url") and re.search(r"\.(jpg|jpeg|png|webp)$", info.get("url"), re.I):
                    candidates.append(info.get("url"))
                if info.get("thumbnail"):
                    candidates.append(info.get("thumbnail"))
                # sometimes entries have 'thumbnails' list
                if info.get("thumbnails"):
                    for t in info.get("thumbnails"):
                        if isinstance(t, dict) and t.get("url"):
                            candidates.append(t.get("url"))
            # remove duplicates and empty
            candidates = [c for i, c in enumerate(candidates) if c and c not in candidates[:i]]
            # yuklab olish
            for idx, img_url in enumerate(candidates):
                ext = Path(img_url).suffix or ".jpg"
                path = os.path.join(tmpdir, f"img_{idx}{ext}")
                if download_binary(img_url, path):
                    downloaded_files.append(path)
        except Exception as e:
            logger.exception("info orqali image url olish xatosi: %s", e)

    # 4) agar hali topilmagan bo'lsa - instaloader bilan urinish (Instagram postlar uchun)
    if not downloaded_files and "instagram.com" in url:
        try:
            L = instaloader.Instaloader(dirname_pattern=tmpdir, download_videos=True, save_metadata=False, post_metadata_txt_pattern=None)
            # Agar cookiefile mavjud bo'lsa va u instaloader formatida session fayli bo'lsa, ishlatish mumkin. Bu oddiy cookies.txt emas, lekin ko'p hollarda public postlarni yuklash uchun yetadi.
            shortcode = None
            m = re.search(r"(?:/p/|/reel/|/tv/)([^/?#&]+)", url)
            if m:
                shortcode = m.group(1)
            if shortcode:
                post = instaloader.Post.from_shortcode(L.context, shortcode)
                L.download_post(post, target=shortcode)
                downloaded_files = find_media_files(tmpdir)
        except Exception as e:
            logger.exception("instaloader fallback xatosi: %s", e)

    # 5) tanlab olingan eng mos fayl
    if downloaded_files:
        # eng katta faylni olamiz (odatda video bo'ladi)
        chosen = max(downloaded_files, key=lambda p: Path(p).stat().st_size)
        # MIME turini taxmin qilamiz
        ext = Path(chosen).suffix.lower()
        if ext in [".jpg", ".jpeg", ".png", ".webp"]:
            mtype = "photo"
        elif ext in [".mp3", ".m4a", ".aac", ".ogg"]:
            mtype = "audio"
        else:
            mtype = "video"
        # agar juda katta bo'lsa, qaytarish
        size = Path(chosen).stat().st_size
        if size > MAX_TELEGRAM_BYTES:
            # tozalash vaqtincha papkani qoldiramiz, lekin faylni o'chiramiz
            msg = f"Fayl juda katta: {sizeof_fmt(size)}. Telegram limitidan oshib ketdi."
            shutil.rmtree(tmpdir, ignore_errors=True)
            return None, msg
        return chosen, mtype

    # 6) hech narsa topilmasa, tozalab xatolik qaytaramiz
    shutil.rmtree(tmpdir, ignore_errors=True)
    return None, "Media topilmadi yoki public bo'lmagan/private post. Agar private bo'lsa, COOKIES_TXT ni sozlang."

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
    # saqlaymiz va uid yuboramiz (callback_data kichik bo'ladi)
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
    # foydalanuvchiga xabar
    try:
        query.edit_message_text("⏳ Yuklanmoqda... Iltimos kuting.")
    except Exception:
        pass

    # fetch
    file_path, info = fetch_media(url, choice)
    if not file_path:
        try:
            query.message.reply_text(f"❌ Xatolik: {info}")
        except Exception:
            pass
        return

    # yuborish
    try:
        with open(file_path, "rb") as fh:
            if info == "photo":
                query.message.reply_photo(photo=fh)
            elif info == "audio":
                query.message.reply_audio(audio=fh)
            else:
                # video yoki boshqa media
                query.message.reply_video(video=fh)
    except Exception as e:
        logger.exception("Yuborishda xato: %s", e)
        try:
            query.message.reply_text(f"❌ Faylni yuborishda xato: {e}")
        except Exception:
            pass
    finally:
        # oxirida papkani tozalash: fetch_media tmp papkani o'chirolmagan bo'lsa uni ham o'chirishga urin
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
