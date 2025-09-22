import re
from telegram.ext import Updater, MessageHandler, Filters
import yt_dlp
import os

# Bu yerga o'zingizning bot tokeningizni yozing
BOT_TOKEN = "8467004923:AAGf6E3gcaCbyljcpUKBJ5BLQL8JX2P5PnM"

def extract_url(text: str) -> str | None:
    """
    Foydalanuvchi yuborgan matndan http yoki https bilan boshlanuvchi
    haqiqiy URLni qidirib topadi.
    """
    pattern = r"(https?://[^\s]+)"
    match = re.search(pattern, text)
    if match:
        # Oxirida vergul yoki nuqta bo'lsa olib tashlaymiz
        return match.group(0).rstrip('.,)')
    return None

def download_video(url: str, chat_id: int) -> str:
    """
    YouTube linkni yuklab olish.
    """
    ydl_opts = {
        'outtmpl': f'{chat_id}.%(ext)s',
        'format': 'mp4',
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return f"{chat_id}.{info['ext']}"

def handle_message(update, context):
    text = update.message.text

    url = extract_url(text)
    if not url:
        update.message.reply_text("❗️ Havola topilmadi. Iltimos to‘g‘ri link yuboring.")
        return

    update.message.reply_text("⏳ Video yuklab olinmoqda, biroz kuting…")

    try:
        file_path = download_video(url, update.message.chat_id)
        with open(file_path, 'rb') as f:
            update.message.reply_video(video=f)
        os.remove(file_path)
    except Exception as e:
        update.message.reply_text(f"❌ Xatolik: {e}")

def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
