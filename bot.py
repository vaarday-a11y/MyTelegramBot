import logging, os, re
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackQueryHandler, Filters
import yt_dlp

# Telegram token (Railway Variables ichida TELEGRAM_TOKEN qilib qo‘yasiz)
TOKEN = os.getenv("TELEGRAM_TOKEN")
updater = Updater(TOKEN, use_context=True)

logging.basicConfig(level=logging.INFO)

def start(update, context):
    update.message.reply_text(
        "👋 Salom! Menga YouTube, TikTok yoki Instagram link yuboring.\n"
        "So‘ng video yoki mp3 formatini tanlashingiz mumkin."
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

    # Cookies.txt Railway Variables orqali olinadi
    cookies_path = "cookies.txt"
    if os.getenv("COOKIES_TXT"):
        with open(cookies_path, "w", encoding="utf-8") as f:
            f.write(os.getenv("COOKIES_TXT"))

    if choice == "video":
        ydl_opts = {
            "format": "bestvideo+bestaudio/best",
            "merge_output_format": "mp4",
            "outtmpl": "%(id)s.%(ext)s",
            "overwrites": True,
        }
        if os.path.exists(cookies_path):
    ydl_opts["cookiefile"] = cookies_path
    else:  # audio
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": "audio.%(ext)s",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        }
        if os.path.exists(cookies_path):
    ydl_opts["cookiefile"] = cookies_path
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
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_link))
    dp.add_handler(CallbackQueryHandler(button_handler))
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
