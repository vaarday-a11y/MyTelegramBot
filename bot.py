import logging
import os
import re
import uuid
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackQueryHandler, Filters, CallbackContext
import yt_dlp

# 🔹 Logging sozlamasi
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# 🔹 Token olish
TOKEN = os.environ.get("BOT_TOKEN")

# 🔹 URL saqlash uchun global storage
URL_STORE = {}


# 🔹 Start komandasi
def start(update: Update, context: CallbackContext):
    update.message.reply_text(
        "👋 Salom! Men Instagram, TikTok va YouTube’dan video/audio yuklab bera olaman.\n\n"
        "Menga faqat havolani yuboring!"
    )


# 🔹 Havolani aniqlash
def handle_link(update: Update, context: CallbackContext):
    text = update.message.text or ""
    urls = re.findall(r"(https?://\S+|www\.\S+)", text)
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

    # 🔹 unique id yaratamiz va URLni saqlaymiz
    uid = uuid.uuid4().hex
    URL_STORE[uid] = url

    keyboard = [
        [
            InlineKeyboardButton("🎥 Video (MP4)", callback_data=f"video|{uid}"),
            InlineKeyboardButton("🎵 Audio (MP3)", callback_data=f"audio|{uid}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(
        f"✅ {platform} havolasi aniqlandi. Yuklab olish turini tanlang 👇",
        reply_markup=reply_markup
    )


# 🔹 Tugma bosilganda ishlaydi
def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    if not query:
        return
    try:
        query.answer()
    except Exception:
        pass

    data = query.data or ""
    if "|" not in data:
        query.message.reply_text("❌ Noto'g'ri so'rov.")
        return

    choice, uid = data.split("|", 1)
    uid = uid.strip()
    if uid not in URL_STORE:
        query.message.reply_text("❌ Havola topilmadi yoki eskirgan. Iltimos, qayta yuboring.")
        return

    url = URL_STORE.pop(uid)  # olish va o‘chirish (bir martalik)
    query.message.reply_text("⏳ Yuklab olinmoqda, kuting...")

    # 🔹 yuklash parametrlari
    if choice == "video":
        ydl_opts = {
            "format": "best",
            "outtmpl": "%(title)s.%(ext)s",
            "noplaylist": True,
        }
    else:
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": "%(title)s.%(ext)s",
            "noplaylist": True,
            "postprocessors": [
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}
            ],
        }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_name = ydl.prepare_filename(info)
            if choice == "audio":
                file_name = os.path.splitext(file_name)[0] + ".mp3"

        # 🔹 Foydalanuvchiga faylni yuborish
        with open(file_name, "rb") as f:
            if choice == "video":
                query.message.reply_video(f)
            else:
                query.message.reply_audio(f)

        os.remove(file_name)  # vaqtinchalik faylni o‘chirib tashlash

    except Exception as e:
        logger.error(f"Yuklab olishda xato: {e}")
        query.message.reply_text(f"❌ Xatolik: {str(e)}")


# 🔹 Asosiy funksiyani ishga tushirish
def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_link))
    dp.add_handler(CallbackQueryHandler(button_handler))

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
