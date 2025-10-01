import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackQueryHandler, Filters, CallbackContext
import yt_dlp

# Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables
TOKEN = os.environ.get("TELEGRAM_TOKEN")
COOKIES_FILE = os.environ.get("COOKIES_TXT")

# Start command
def start(update: Update, context: CallbackContext):
    update.message.reply_text(
        "Salom! Video, audio yoki rasm linkini yuboring.\n"
        "Men sizga yuklab beraman."
    )

# Function to handle messages (Instagram/YouTube links)
def handle_message(update: Update, context: CallbackContext):
    url = update.message.text.strip()
    
    # Create buttons for type selection
    keyboard = [
        [InlineKeyboardButton("Video 🎥", callback_data=f"video|{url}")],
        [InlineKeyboardButton("Audio 🎵", callback_data=f"audio|{url}")],
        [InlineKeyboardButton("Rasm 🖼️", callback_data=f"image|{url}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text("Qaysi formatda yuklab olishni xohlaysiz?", reply_markup=reply_markup)

# Callback for button presses
def button_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    data = query.data
    action, url = data.split("|", 1)
    
    ydl_opts = {
        'outtmpl': '%(title)s.%(ext)s',
    }

    # Agar cookies fayli mavjud bo'lsa, qo'shamiz
    if COOKIES_FILE:
        ydl_opts['cookiefile'] = COOKIES_FILE

    # Foydalanuvchiga formatga qarab yuklash
    if action == "video":
        ydl_opts['format'] = 'bestvideo+bestaudio/best'
    elif action == "audio":
        ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]
    elif action == "image":
        ydl_opts['skip_download'] = False
        ydl_opts['writethumbnail'] = True
        ydl_opts['skip_download'] = True  # faqat rasm olish uchun

    try:
        query.edit_message_text("Yuklanmoqda, biroz kuting...")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info_dict)

        # Video yoki audio yuborish
        if action == "video":
            context.bot.send_video(chat_id=query.message.chat_id, video=open(filename, 'rb'))
        elif action == "audio":
            context.bot.send_audio(chat_id=query.message.chat_id, audio=open(filename.replace('.webm', '.mp3'), 'rb'))
        elif action == "image":
            # Thumbnail faylini topish
            thumbnail = info_dict.get('thumbnail')
            if thumbnail:
                context.bot.send_photo(chat_id=query.message.chat_id, photo=thumbnail)
            else:
                context.bot.send_message(chat_id=query.message.chat_id, text="Rasm topilmadi.")

    except Exception as e:
        logger.error(e)
        query.edit_message_text(f"❌ Xatolik yuz berdi: {e}")

def main():
    if not TOKEN:
        logger.error("TELEGRAM_TOKEN variable aniqlanmadi!")
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
