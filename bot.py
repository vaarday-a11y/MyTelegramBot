import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
import yt_dlp
import os

# Tokeningizni shu yerga yozing
TOKEN = "8467004923:AAGf6E3gcaCbyljcpUKBJ5BLQL8JX2P5PnM"

logging.basicConfig(level=logging.INFO)

# /start komandasi
def start(update, context):
    update.message.reply_text("Salom! Menga YouTube, TikTok yoki Instagram link yuboring.")

# Link kelganda tugmalar chiqishi
def handle_link(update, context):
    url = update.message.text
    context.user_data["last_url"] = url  # linkni vaqtincha saqlab qo‘yamiz

    keyboard = [
        [
            InlineKeyboardButton("🎥 Video (MP4)", callback_data="video"),
            InlineKeyboardButton("🎵 Audio (MP3)", callback_data="audio")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("Qaysi formatda yuklab olasiz?", reply_markup=reply_markup)

# Tugmalar bosilganda yuklab berish
def button_handler(update, context):
    query = update.callback_query
    choice = query.data
    url = context.user_data.get("last_url")  # tugma bosilganda linkni qaytarib olamiz

    if not url:
        query.message.reply_text("❌ Xatolik: link topilmadi.")
        return

    if choice == "video":
        ydl_opts = {
            "format": "bestvideo+bestaudio/best",
            "merge_output_format": "mp4",
            "outtmpl": "output.%(ext)s"
        }
    else:
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": "output.%(ext)s",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_name = ydl.prepare_filename(info)
            if choice == "audio":
                file_name = os.path.splitext(file_name)[0] + ".mp3"

        query.message.reply_document(document=open(file_name, "rb"))
        os.remove(file_name)
    except Exception as e:
        query.message.reply_text(f"❌ Xatolik: {e}")

# Asosiy funksiya
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
