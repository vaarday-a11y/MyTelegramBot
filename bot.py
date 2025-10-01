import logging, os, re
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackQueryHandler, Filters
import yt_dlp

TOKEN = os.getenv("TELEGRAM_TOKEN")  # Variables dagi key nomi bilan bir xil bo‘lishi kerak!

logging.basicConfig(level=logging.INFO)

def start(update, context):
    update.message.reply_text(
        "Salom! Menga YouTube, TikTok yoki Instagram link yuboring.\n"
        "Keyin video yoki mp3 formatini tanlashingiz mumkin."
    )

def handle_link(update, context):
    text = update.message.text
    urls = re.findall(r'(https?://\S+)', text)
    if not urls:
        update.message.reply_text("❌ Faqat haqiqiy link yuboring.")
        return

    url = urls[0]

    keyboard = [
        [
            InlineKeyboardButton("🎥 Video (MP4)", callback_data=f"video|{url}"),
            InlineKeyboardButton("🎵 Audio (MP3)", callback_data=f"audio|{url}")
        ]
    ]
    update.message.reply_text(
        "Qaysi formatda yuklab olasiz?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

def button_handler(update, context):
    query = update.callback_query
    query.answer()
    choice, url = query.data.split("|")

    # Instagram uchun ham ishlaydigan umumiy sozlamalar
    common_opts = {
        "outtmpl": "%(id)s.%(ext)s",
        "overwrites": True,
        "quiet": True,
        "noplaylist": True,
        "cookiesfrombrowser": ("chrome",),   # instagram uchun foydali
        "http_headers": {"User-Agent": "Mozilla/5.0"},  # bloklanmasligi uchun
    }

    if choice == "video":
        ydl_opts = {
            **common_opts,
            "format": "bestvideo+bestaudio/best",
            "merge_output_format": "mp4",
        }
    else:  # audio
        ydl_opts = {
            **common_opts,
            "format": "bestaudio/best",
            "outtmpl": "audio.%(ext)s",
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
