import os
import telebot
import yt_dlp

TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start_cmd(message):
    bot.reply_to(
        message, 
        "Привет! Напиши мне название песни или исполнителя, и я пришлю MP3 файл прямо в этот чат."
    )

@bot.message_handler(func=lambda message: True)
def download_and_send_audio(message):
    query = message.text
    status_msg = bot.reply_to(message, f"🔎 Ищу и скачиваю: *{query}*...", parse_mode="Markdown")

    filename = f"song_{message.chat.id}.mp3"

    ydl_opts = {
        'format': 'bestaudio/best',
        'default_search': 'ytsearch1',
        'outtmpl': filename,
        'quiet': True,
        'noplaylist': True,
        'nocheckcertificate': True,
        'geo_bypass': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{query}", download=True)
            if 'entries' in info and len(info['entries']) > 0:
                video_info = info['entries'][0]
            else:
                video_info = info

            title = video_info.get('title', query)
            uploader = video_info.get('uploader', 'MuzoBot')

        if os.path.exists(filename):
            with open(filename, 'rb') as audio_file:
                bot.send_audio(
                    chat_id=message.chat.id,
                    audio=audio_file,
                    title=title,
                    performer=uploader,
                    reply_to_message_id=message.message_id
                )
            bot.delete_message(chat_id=message.chat.id, message_id=status_msg.message_id)
        else:
            raise Exception("Файл не сохранился")

    except Exception as e:
        print(f"Ошибка загрузки: {e}")
        bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=status_msg.message_id,
            text="❌ Не удалось скачать файл. Попробуйте ввести более точное название песни и исполнителя."
        )

    if os.path.exists(filename):
        os.remove(filename)

bot.infinity_polling()
