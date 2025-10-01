import logging
import os
import re
import tempfile
import shutil
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackQueryHandler, Filters
import yt_dlp

# -------------------------
# Konfiguratsiya
# -------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    logger.error("TELEGRAM_TOKEN muhit o'zgaruvchisi topilmadi. Iltimos Railway/ENV ga qo'shing.")
    raise SystemExit("Missing TELEGRAM_TOKEN")

# Telegram orqali yuborishga ruxsat etilgan maksimal fayl hajmini baytlarda sozlang (default 50 MB)
MAX_TELEGRAM_FILESIZE = int(os.getenv("MAX_TELEGRAM_MAX_BYTES", 50 * 1024 * 1024))

# Updater/Dispatcher (python-telegram-bot v13)
updater = Updater(TOKEN, use_context=True)


# -------------------------
# Yordamchi funksiyalar
# -------------------------
def sizeof_fmt(num, suffix="B"):
    for unit in ["", "K", "M", "G", "T"]:
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Y{suffix}"


def find_largest_file_in_dir(d):
    files = [p for p in Path(d).iterdir() if p.is_file()]
    if not files:
        return None
    # qaytargan eng katta fayl
    return max(files, key=lambda p: p.stat().st_size)


# -------------------------
# Handlers
# -------------------------
def start(update, context):
    update.message.reply_text(
        "👋 Salom! Menga YouTube, TikTok yoki Instagram link yuboring.\n"
        "So‘ng video yoki mp3 formatini tanlashingiz mumkin."
    )


def handle_link(update, context):
    text = update.message.text or ""
    # https:// yoki www. bilan boshlanuvchi linklarni ushlab olamiz
    urls = re.findall(r'(https?://\S+|www\.\S+)', text)
    if not urls:
        update.message.reply_text("❌ Iltimos, to‘liq havola yuboring.")
        return

    url = urls[0].strip()

    if "instagram.com" in url:
        platform = "Instagram"
    elif "tiktok.com" in url:
        platform = "TikTok"
    elif "youtube.com" in url or "youtu.be" in url:
        platform = "YouTube"
    else:
        update.message.reply_text("❌ Bu platforma qo‘llab-quvvatlanmaydi.")
        return

    keyboard = [
        [
            InlineKeyboardButton("🎥 Video (MP4)", callback_data=f"video|{url}"),
            InlineKeyboardButton("🎵 Audio (MP3)", callback_data=f"audio|{url}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    update.message.reply_text(
        f"✅ {platform} havolasi aniqlandi. Yuklab olish turini tanlang 👇",
        reply_markup=reply_markup
    )


def button_handler(update, context):
    query = update.callback_query
    if not query:
        return
    try:
        query.answer()
    except Exception:
        pass

    # callback_data: "video|<url>" yoki "audio|<url>"
    data = query.data or ""
    if "|" not in data:
        query.message.reply_text("❌ Noto'g'ri so'rov.")
        return

    choice, url = data.split("|", 1)
    choice = choice.strip()
    url = url.strip()

    # vaqtinchalik katalog yaratamiz
    tmpdir = tempfile.mkdtemp(prefix="yt_")
    cookiefile_path = None

    # 1) Agar repository ichida cookies.txt bo'lsa uni ishlatamiz (faqat o'zingizni cookie)
    repo_cookie = Path(__file__).parent / "cookies.txt"
    if repo_cookie.exists():
        cookiefile_path = str(repo_cookie)

    # 2) Agar COOKIES_TXT atrof-muhit o'zgaruvchisi bo'lsa — vaqtinchalik faylga yozamiz
    elif os.getenv("COOKIES_TXT"):
        cookiefile_path = os.path.join(tmpdir, "cookies.txt")
        try:
            with open(cookiefile_path, "w", encoding="utf-8") as f:
                f.write(os.getenv("COOKIES_TXT"))
        except Exception as e:
            logger.exception("COOKIES_TXT yozishda muammo:")
            cookiefile_path = None

    # YTDLP options — umumiy
    out_template = os.path.join(tmpdir, "%(id)s.%(ext)s")
    ydl_opts = {
        "outtmpl": out_template,
        "noplaylist": True,
        "ignoreerrors": True,
        "no_warnings": True,
        # "quiet": True,  # agar siz konsol loglarini kamroq ko'rmoqchi bo'lsangiz yoqing
        "restrictfilenames": True,
    }

    # formatlar
    if choice == "video":
        ydl_opts["format"] = "bestvideo+bestaudio/best"
        # merged mp4 chiqadi agar kerak bo'lsa
        ydl_opts["merge_output_format"] = "mp4"
    else:  # audio
        ydl_opts["format"] = "bestaudio/best"
        ydl_opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]

    # cookiefile mavjud bo'lsa to'g'ri kalit nomi bilan yuboramiz
    if cookiefile_path:
        ydl_opts["cookiefile"] = cookiefile_path

    # Foydalanuvchiga boshlanish haqida xabar
    try:
        query.message.reply_text("⏳ Yuklanmoqda — biroz kuting...")
    except Exception:
        pass

    downloaded_file = None
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            # prepare_filename ko'pincha boshlang'ich faylni ko'rsatadi
            candidate = ydl.prepare_filename(info) if info else None

        # Agar postprocessor mp3 yaratgan bo'lsa — .mp3 ni tekshiramiz
        if choice == "audio" and candidate:
            candidate_mp3 = os.path.splitext(candidate)[0] + ".mp3"
            if os.path.exists(candidate_mp3):
                downloaded_file = candidate_mp3
            elif os.path.exists(candidate):
                downloaded_file = candidate
        # video yoki default
        if not downloaded_file:
            found = find_largest_file_in_dir(tmpdir)
            if found:
                downloaded_file = str(found)

        if not downloaded_file or not os.path.exists(downloaded_file):
            query.message.reply_text("❌ Yuklash muvaffaqiyatsiz — fayl topilmadi. Ehtimol link maxfiy yoki yt-dlp extractor o'zgargan.")
            return

        file_size = os.path.getsize(downloaded_file)
        logger.info("Downloaded file: %s (%s)", downloaded_file, sizeof_fmt(file_size))

        if file_size > MAX_TELEGRAM_FILESIZE:
            query.message.reply_text(
                f"❌ Fayl juda katta: {sizeof_fmt(file_size)}. Bot orqali yuborish limitidan oshib ketdi.\n"
                "Iltimos: 1) Faylni bulutga (Google Drive/Dropbox) yuklab havolasini yuboring, yoki 2) audio (mp3) sifatida yuklab ko'ring."
            )
            return

        # Faylni yuborish
        with open(downloaded_file, "rb") as f:
            filename = os.path.basename(downloaded_file)
            query.message.reply_document(document=f, filename=filename)

    except Exception as e:
        logger.exception("Yuklash/yuborishda xatolik")
        try:
            query.message.reply_text(f"❌ Xatolik yuz berdi: {e}")
        except Exception:
            pass
    finally:
        # tozalash
        try:
            if os.path.exists(tmpdir):
                shutil.rmtree(tmpdir)
        except Exception:
            logger.exception("Tmp papkani tozalashda muammo")


def main():
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_link))
    dp.add_handler(CallbackQueryHandler(button_handler))
    updater.start_polling()
    logger.info("Bot ishga tushdi.")
    updater.idle()


if __name__ == "__main__":
    main()
