import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, CallbackContext
import yt_dlp

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Environment variables
TOKEN = os.getenv("TOKEN")  # Telegram bot token
COOKIES_FILE = os.getenv("COOKIES_FILE", "cookies.txt")  # Instagram cookies file

# Download function
def download_media(url: str, media_type="video"):
    ydl_opts = {
        'outtmpl': 'downloads/%(title)s.%(ext)s',
        'cookiefile': COOKIES_FILE,
    }

    if media_type == "audio":
        ydl_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192'
            }]
        })
    elif media_type == "image":
        # Rasm uchun video emas, faqat image yozadi
        ydl_opts.update({
            'skip_download': False,
            'writesubtitles': False,
            'format': 'bestvideo[ext=mp4]+bestaudio/best'
        })

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        if media_type == "audio":
            filename = os.path.splitext(filename)[0] + ".mp3"
        return filename

# Handlers
def start(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("Video", callback_data='video')],
        [InlineKeyboardButton("Audio", callback_data='audio')],
        [InlineKeyboardButton("Rasm", callback_data='image')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("Nimani yuklab olamiz?", reply_markup=reply_markup)

def button(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    context.user_data['media_type'] = query.data
    query.edit_message_text(text=f"Endi linkni yuboring ({query.data})")

def handle_message(update: Update, context: CallbackContext):
    url = update.message.text
    media_type = context.user_data.get('media_type', 'video')
    try:
        update.message.reply_text(f"{media_type} yuklanmoqda... ⏳")
        file_path = download_media(url, media_type)
        with open(file_path, 'rb') as f:
            if media_type == "audio":
                update.message.reply_audio(f)
            elif media_type == "image":
                update.message.reply_photo(f)
            else:
                update.message.reply_video(f)
    except Exception as e:
        update.message.reply_text(f"❌ Xatolik: {str(e)}")

# Main
def main():
    if not TOKEN:
        logger.error("TOKEN topilmadi. Environment variable qo‘shing!")
        return

    if not os.path.exists("downloads"):
        os.makedirs("downloads")

    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(button))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    updater.start_polling()
    logger.info("Bot ishga tushdi!")
    updater.idle()

if __name__ == '__main__':
    main()
