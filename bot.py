import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackQueryHandler, Filters, CallbackContext
import yt_dlp

# Telegram tokeningizni shu yerga yozing
TOKEN = "SIZNING_BOT_TOKEN"

# Instagram cookies fayli shu nomda bo'lishi kerak
COOKIES_FILE = "cookies.txt"

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def start(update: Update, context: CallbackContext):
    update.message.reply_text("Salom! Link yuboring (Instagram/TikTok/YouTube) va video, audio yoki rasmni tanlang.")

def handle_link(update: Update, context: CallbackContext):
    url = update.message.text
    keyboard = [
        [InlineKeyboardButton("Video", callback_data=f"video|{url}")],
        [InlineKeyboardButton("Audio", callback_data=f"audio|{url}")],
        [InlineKeyboardButton("Rasm", callback_data=f"image|{url}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("Formatni tanlang:", reply_markup=reply_markup)

def download_media(url, download_type):
    ydl_opts = {
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
        'quiet': True,
    }

    # Agar Instagram bo'lsa cookies qo'shish
    if "instagram.com" in url.lower():
        ydl_opts['cookiefile'] = COOKIES_FILE

    if download_type == "audio":
        ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    elif download_type == "video":
        ydl_opts['format'] = 'bestvideo+bestaudio/best'
    elif download_type == "image":
        ydl_opts['format'] = 'bestvideo/best'
        ydl_opts['skip_download'] = True  # Rasmni olish uchun

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        if download_type == "image":
            # Instagram postdagi rasm
            if 'entries' in info:
                image_url = info['entries'][0]['url']
            else:
                image_url = info['url']
            return image_url
        filename = ydl.prepare_filename(info)
        if download_type == "audio":
            filename = os.path.splitext(filename)[0] + ".mp3"
        return filename

def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    data = query.data.split("|")
    download_type, url = data[0], data[1]
    query.edit_message_text(text="Yuklanmoqda... Iltimos kuting ⏳")
    try:
        file_path = download_media(url, download_type)
        if download_type == "image":
            query.message.reply_photo(file_path)
        else:
            query.message.reply_document(open(file_path, 'rb'))
    except Exception as e:
        query.message.reply_text(f"❌ Xatolik: {e}")

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
