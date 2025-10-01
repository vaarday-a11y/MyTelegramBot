import logging
import os
import yt_dlp
import instaloader
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

TOKEN = os.getenv("BOT_TOKEN")  # Railway/GitHub Secrets da BOT_TOKEN sifatida qo'ygan bo'lishing kerak

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

logger = logging.getLogger(__name__)

def start(update: Update, context: CallbackContext):
    update.message.reply_text("Salom! Menga YouTube yoki Instagram havolasini yuboring.")

def download_youtube(url):
    ydl_opts = {
        'format': 'best',
        'outtmpl': 'downloads/%(title)s.%(ext)s'
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)

def download_instagram(url):
    try:
        # Avval video/reels tekshiramiz
        ydl_opts = {
            'outtmpl': 'downloads/%(title)s.%(ext)s',
            'format': 'best'
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info)

    except Exception as e:
        # Agar video bo'lmasa, rasmni olishga harakat qilamiz
        try:
            loader = instaloader.Instaloader(dirname_pattern="downloads", download_videos=False, save_metadata=False)
            post = instaloader.Post.from_shortcode(loader.context, url.split("/")[-2])
            file_list = []
            if post.typename == "GraphImage":
                loader.download_post(post, target="downloads")
                file_list.append(f"downloads/{post.owner_username}/{post.date_utc.strftime('%Y-%m-%d_%H-%M-%S_UTC')}.jpg")
            elif post.typename == "GraphSidecar":
                for i, node in enumerate(post.get_sidecar_nodes()):
                    loader.download_post(post, target="downloads")
                    file_list.append(f"downloads/{post.owner_username}/{post.date_utc.strftime('%Y-%m-%d_%H-%M-%S_UTC')}_{i+1}.jpg")
            return file_list
        except Exception as ex:
            return str(ex)

def handle_message(update: Update, context: CallbackContext):
    url = update.message.text
    chat_id = update.message.chat_id

    if "youtube.com" in url or "youtu.be" in url:
        try:
            file_path = download_youtube(url)
            context.bot.send_video(chat_id=chat_id, video=open(file_path, 'rb'))
        except Exception as e:
            update.message.reply_text(f"❌ Xatolik: {e}")

    elif "instagram.com" in url:
        result = download_instagram(url)
        if isinstance(result, list):  # agar rasm(lar)
            for f in result:
                context.bot.send_photo(chat_id=chat_id, photo=open(f, 'rb'))
        elif isinstance(result, str):  # agar xatolik bo'lsa
            update.message.reply_text(f"❌ Xatolik: {result}")
        else:  # video/reels
            context.bot.send_video(chat_id=chat_id, video=open(result, 'rb'))
    else:
        update.message.reply_text("Faqat YouTube va Instagram havolalarini yuboring.")

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
