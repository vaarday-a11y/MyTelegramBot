import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackQueryHandler, CallbackContext, Filters
import yt_dlp

# Logging sozlamalari
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# TOKEN environment variable orqali olinadi (Railway-da sozla)
TOKEN = os.getenv("TELEGRAM_TOKEN")

# Cookies fayl manzili (agar Instagram login kerak bo'lsa)
COOKIES = os.getenv("COOKIES_TXT")  # misol: "cookies.txt"

def start(update: Update, context: CallbackContext):
    update.message.reply_text(
        "Salom! Video yoki rasm havolasini yuboring.\n"
        "Menga YouTube, TikTok yoki Instagram linkini yuborishingiz mumkin."
    )

def download_media(url: str, media_type: str):
    """Video yoki audio yoki rasmni yuklab olish"""
    ydl_opts = {
        'format': 'best',
        'outtmpl': 'download.%(ext)s',
        'noplaylist': True
    }

    # Cookies qo‘shish (faqat Instagram uchun)
    if COOKIES and "instagram.com" in url:
        ydl_opts['cookiefile'] = COOKIES

    # Agar audio tanlansa
    if media_type == "audio":
        ydl_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        })

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        if media_type == "audio":
            filename = filename.rsplit(".", 1)[0] + ".mp3"
        return filename

def handle_message(update: Update, context: CallbackContext):
    url = update.message.text.strip()
    keyboard = [
        [
            InlineKeyboardButton("Video", callback_data=f"video|{url}"),
            InlineKeyboardButton("Audio", callback_data=f"audio|{url}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("Nimani yuklab olamiz?", reply_markup=reply_markup)

def button_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    data = query.data
    media_type, url = data.split("|", 1)
    
    message = query.edit_message_text(text=f"{media_type.capitalize()} yuklanmoqda... 🔄")
    try:
        file_path = download_media(url, media_type)
        with open(file_path, "rb") as f:
            if media_type == "audio":
                context.bot.send_audio(chat_id=query.message.chat_id, audio=f)
            else:
                context.bot.send_document(chat_id=query.message.chat_id, document=f)
        os.remove(file_path)
        message.edit_text(f"{media_type.capitalize()} yuklandi ✅")
    except Exception as e:
        logger.error(e)
        message.edit_text(f"❌ Xatolik: {str(e)}")

def main():
    if not TOKEN:
        logger.error("TOKEN environment variable o'rnatilmagan!")
        return

    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    dp.add_handler(CallbackQueryHandler(button_callback))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
