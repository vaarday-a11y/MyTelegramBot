import os
import logging
import yt_dlp
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackContext,
    CallbackQueryHandler,
)

# Logging sozlamalari
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Telegram TOKEN va cookies.txt yo‘lini o‘qish
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
COOKIES_FILE = os.getenv("COOKIES_TXT", "cookies.txt")

# Maksimal fayl limiti (Telegram 2GB gacha ruxsat beradi, lekin biz xavfsizroq qilish uchun 1.9GB)
MAX_FILE_SIZE = 1900 * 1024 * 1024  


# Start komandasi
def start(update: Update, context: CallbackContext):
    update.message.reply_text("Salom 👋 Video yoki rasm linkini yuboring.")


# Tugmalar yasash (video/audio)
def get_format_keyboard(url):
    keyboard = [
        [
            InlineKeyboardButton("🎥 Video", callback_data=f"video|{url}"),
            InlineKeyboardButton("🎵 Audio", callback_data=f"audio|{url}"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


# Foydalanuvchi link yuborganda
def handle_message(update: Update, context: CallbackContext):
    url = update.message.text

    if "instagram.com" in url or "youtu" in url or "tiktok.com" in url:
        update.message.reply_text(
            "Qaysi formatda yuklamoqchisiz?", reply_markup=get_format_keyboard(url)
        )
    else:
        update.message.reply_text("❌ Noto‘g‘ri link yubordingiz.")


# Yuklash funksiyasi
def download_and_send(update: Update, context: CallbackContext, url, download_audio=False):
    chat_id = update.effective_chat.id
    msg = context.bot.send_message(chat_id, "⏳ Yuklanmoqda...")

    ydl_opts = {
        "outtmpl": "%(title)s.%(ext)s",
        "cookiefile": COOKIES_FILE if os.path.exists(COOKIES_FILE) else None,
    }

    if download_audio:
        ydl_opts.update(
            {
                "format": "bestaudio/best",
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
            }
        )
    else:
        ydl_opts.update({"format": "best"})

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_name = ydl.prepare_filename(info)

        # Fayl hajmini tekshiramiz
        file_size = os.path.getsize(file_name)
        if file_size > MAX_FILE_SIZE:
            msg.edit_text("⚠️ Fayl juda katta. Uni to‘g‘ridan-to‘g‘ri yuklab olmaysiz.\n\n"
                          f"👉 Bu yerdan yuklab oling: {info.get('url', url)}")
            os.remove(file_name)
            return

        # Faylni yuborish
        with open(file_name, "rb") as f:
            if download_audio:
                context.bot.send_audio(chat_id=chat_id, audio=f)
            else:
                if file_name.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                    context.bot.send_photo(chat_id=chat_id, photo=f)
                else:
                    context.bot.send_video(chat_id=chat_id, video=f)

        msg.edit_text("✅ Yuklab berildi!")
        os.remove(file_name)

    except Exception as e:
        msg.edit_text(f"❌ Xatolik: {str(e)}")


# Tugmalarni ishlash
def button(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    action, url = query.data.split("|")

    if action == "video":
        download_and_send(update, context, url, download_audio=False)
    elif action == "audio":
        download_and_send(update, context, url, download_audio=True)


def main():
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    dp.add_handler(CallbackQueryHandler(button))

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
