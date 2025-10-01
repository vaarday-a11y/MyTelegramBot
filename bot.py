import os
import yt_dlp
import logging
import requests
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

# TOKENni Railway environment variable'dan olish
TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN environment variable topilmadi!")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

def start(update: Update, context: CallbackContext):
    update.message.reply_text("Salom 👋 Men Instagram, YouTube va TikTok’dan video va rasm yuklab bera olaman!\nLink yuboring 🔗")

def download_media(update: Update, context: CallbackContext):
    url = update.message.text.strip()
    chat_id = update.message.chat_id

    try:
        if "instagram.com" in url:
            ydl_opts = {"format": "best", "outtmpl": "download.%(ext)s"}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                file_path = ydl.prepare_filename(info)
            with open(file_path, "rb") as f:
                if file_path.endswith((".mp4", ".mkv", ".webm")):
                    context.bot.send_video(chat_id=chat_id, video=f)
                else:
                    context.bot.send_photo(chat_id=chat_id, photo=f)
            os.remove(file_path)
        else:
            ydl_opts = {"format": "best", "outtmpl": "download.%(ext)s"}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                file_path = ydl.prepare_filename(info)
            with open(file_path, "rb") as f:
                if file_path.endswith((".mp4", ".mkv", ".webm")):
                    context.bot.send_video(chat_id=chat_id, video=f)
                else:
                    context.bot.send_photo(chat_id=chat_id, photo=f)
            os.remove(file_path)
    except Exception as e:
        update.message.reply_text(f"❌ Xatolik: {str(e)}")

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, download_media))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
