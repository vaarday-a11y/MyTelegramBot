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

    # URLni aniqlash (https:// yoki www. bilan boshlansa ham ushlaydi)
    urls = re.findall(r'(https?://\S+|www\.\S+)', text)
    
    if not urls:
        update.message.reply_text("❌ Iltimos, to‘liq havola yuboring.")
        return

    url = urls[0]

    # Qaysi platformadan ekanini aniqlash
    if "instagram.com" in url:
        platform = "Instagram"
    elif "tiktok.com" in url:
        platform = "TikTok"
    elif "youtube.com" in url or "youtu.be" in url:
        platform = "YouTube"
    else:
        update.message.reply_text("❌ Bu platforma qo‘llab-quvvatlanmaydi.")
        return

    # Tugmalar chiqarish
    keyboard = [
        [
            InlineKeyboardButton("🎥 Video (MP4)", callback_data=f"video|{url}"),
            InlineKeyboardButton("🎵 Audio (MP3)", callback_data=f"audio|{url}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    update.message.reply_text(
        f"✅ {platform} havolasi aniqlandi. Yuklab olish turini tanlang 👇",
        reply_markup=reply_markup
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
        }
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

    # 🔹 Instagram uchun cookies.txt ishlatish
    cookies_path = os.path.join(os.path.dirname(__file__), "cookies.txt")
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
