import os
import telebot
import yt_dlp

TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start_cmd(message):
    bot.reply_to(
        message, 
        "Привет! Напиши мне название песни или исполнителя, и я найду MP3 прямо в этом чате."
    )

@bot.message_handler(func=lambda message: True)
def download_and_send_audio(message):
    query = message.text
    # Отправляем временное сообщение, чтобы пользователь видел статус
    status_msg = bot.reply_to(message, f"🔎 Ищу и скачиваю: *{query}*...", parse_mode="Markdown")

    filename = f"song_{message.message_id}.mp3"

    # Настройки для yt-dlp: поиск первого видео на YouTube и конвертация в MP3
    ydl_opts = {
        'format': 'bestaudio/best',
        'default_search': 'ytsearch1',
        'outtmpl': f'song_{message.message_id}.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': True,
        'noplaylist': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=True)
            if 'entries' in info and len(info['entries']) > 0:
                video_info = info['entries'][0]
            else:
                video_info = info

            title = video_info.get('title', 'Аудиозапись')
            uploader = video_info.get('uploader', 'MuzoBot')

        # Отправляем скачанный MP3-файл прямо в личный чат с пользователем
        with open(filename, 'rb') as audio_file:
            bot.send_audio(
                chat_id=message.chat.id,
                audio=audio_file,
                title=title,
                performer=uploader,
                reply_to_message_id=message.message_id
            )

        # Удаляем временный статус-сообщение
        bot.delete_message(chat_id=message.chat.id, message_id=status_msg.message_id)

    except Exception as e:
        print(f"Ошибка при загрузке: {e}")
        bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=status_msg.message_id,
            text="❌ Не удалось найти или скачать трек. Попробуйте уточнить запрос."
        )

    # Удаляем временный файл с сервера Render, чтобы не забивать память
    if os.path.exists(filename):
        os.remove(filename)

bot.infinity_polling()
