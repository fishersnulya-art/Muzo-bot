import os
import telebot
from telebot import types
import yt_dlp
import imageio_ffmpeg

TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(TOKEN, skip_pending=True)

# Получаем путь к встроенному ffmpeg через python-пакет (работает на Render без системных настроек)
FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()

# Временное хранилище результатов поиска для каждого пользователя
user_data = {}

def get_main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn_top = types.KeyboardButton("🔥 Популярные треки")
    btn_help = types.KeyboardButton("❓ Помощь")
    markup.add(btn_top, btn_help)
    return markup

@bot.message_handler(commands=['start'])
def start_cmd(message):
    welcome_text = (
        f"👋 Привет, *{message.from_user.first_name}*!\n\n"
        "🎵 Я музыкальный бот. Я ищу и скачиваю *полные версии треков* "
        "прямо в плеер Telegram.\n\n"
        "🔍 *Напиши название песни или исполнителя:*"
    )
    bot.send_message(
        message.chat.id, 
        welcome_text, 
        parse_mode="Markdown", 
        reply_markup=get_main_keyboard()
    )

@bot.message_handler(commands=['help'])
@bot.message_handler(func=lambda m: m.text == "❓ Помощь")
def help_cmd(message):
    help_text = (
        "📌 *Как пользоваться ботом:*\n\n"
        "1. Отправь имя артиста или трек (например: `Каспийский груз`).\n"
        "2. Выбери нужный вариант из списка.\n"
        "3. Используй страницы ⬅️ / ➡️, если результатов много.\n"
        "4. Получи полную песню в плеере Telegram!"
    )
    bot.send_message(message.chat.id, help_text, parse_mode="Markdown")

@bot.message_handler(commands=['top'])
@bot.message_handler(func=lambda m: m.text == "🔥 Популярные треки")
def top_music(message):
    search_music_query(message, "русские новинки хиты топ", is_top=True)

@bot.message_handler(func=lambda message: True)
def handle_text_search(message):
    search_music_query(message, message.text)

def search_music_query(message, query, is_top=False):
    status_text = "🔥 Подбираю популярные треки..." if is_top else f"🔎 Ищу полные версии: *{query}*..."
    status_msg = bot.reply_to(message, status_text, parse_mode="Markdown")

    try:
        # Настройки поиска через yt-dlp без скачивания самого файла на этапе поиска
        ydl_opts = {
            'extract_flat': 'in_playlist',
            'default_search': 'ytsearch10' if not is_top else 'ytsearch15',
            'quiet': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            search_result = ydl.extract_info(f"ytsearch15:{query}", download=False)
            entries = search_result.get('entries', [])

        if not entries:
            bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=status_msg.message_id,
                text="❌ Ничего не найдено. Попробуй уточнить запрос."
            )
            return

        tracks = []
        for entry in entries:
            if entry:
                tracks.append({
                    'id': entry.get('id'),
                    'title': entry.get('title', 'Без названия'),
                    'duration': entry.get('duration', 0)
                })

        user_data[message.chat.id] = {
            'tracks': tracks,
            'page': 0
        }

        send_page(message.chat.id, status_msg.message_id)

    except Exception as e:
        print(f"Ошибка поиска: {e}")
        bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=status_msg.message_id,
            text="❌ Произошла ошибка при поиске. Попробуй еще раз."
        )

def send_page(chat_id, message_id):
    data = user_data.get(chat_id)
    if not data:
        return

    tracks = data['tracks']
    page = data['page']
    per_page = 5
    
    start_idx = page * per_page
    end_idx = start_idx + per_page
    current_tracks = tracks[start_idx:end_idx]

    keyboard = types.InlineKeyboardMarkup()

    for idx, track in enumerate(current_tracks):
        global_idx = start_idx + idx
        # Обрезаем слишком длинные названия для кнопок
        title = track['title'][:45] + '...' if len(track['title']) > 45 else track['title']
        button_text = f"🎵 {title}"
        keyboard.add(types.InlineKeyboardButton(text=button_text, callback_data=f"play_{global_idx}"))

    nav_buttons = []
    if page > 0:
        nav_buttons.append(types.InlineKeyboardButton("⬅️ Назад", callback_data="page_prev"))
    
    total_pages = (len(tracks) + per_page - 1) // per_page
    nav_buttons.append(types.InlineKeyboardButton(f"📄 {page + 1}/{total_pages}", callback_data="page_num"))

    if end_idx < len(tracks):
        nav_buttons.append(types.InlineKeyboardButton("Вперед ➡️", callback_data="page_next"))

    keyboard.row(*nav_buttons)

    bot.edit_message_text(
        chat_id=chat_id,
        message_id=message_id,
        text="👇 *Выбери нужный трек из списка:*",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    chat_id = call.message.chat.id
    data = user_data.get(chat_id)

    if call.data == "page_prev":
        if data and data['page'] > 0:
            data['page'] -= 1
            send_page(chat_id, call.message.message_id)
        bot.answer_callback_query(call.id)
        return

    elif call.data == "page_next":
        if data:
            data['page'] += 1
            send_page(chat_id, call.message.message_id)
        bot.answer_callback_query(call.id)
        return

    elif call.data == "page_num":
        bot.answer_callback_query(call.id, text="Используй стрелки для переключения страниц")
        return

    elif call.data.startswith("play_"):
        track_idx = int(call.data.split("_")[1])

        if data and track_idx < len(data['tracks']):
            track = data['tracks'][track_idx]
            video_id = track['id']
            
            bot.answer_callback_query(call.id, text="📥 Скачиваю полную версию трека...")
            bot.send_chat_action(chat_id, 'upload_document')

            filename = f"song_{chat_id}.mp3"

            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': filename.replace('.mp3', ''),
                'ffmpeg_location': FFMPEG_PATH,
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
                    ydl.download([f"https://www.youtube.com/watch?v={video_id}"])

                if os.path.exists(filename):
                    with open(filename, 'rb') as audio_file:
                        bot.send_audio(
                            chat_id=chat_id,
                            audio=audio_file,
                            title=track['title'],
                            performer="MuzoBot",
                            duration=track['duration']
                        )
                else:
                    raise Exception("Файл не конвертировался")

            except Exception as e:
                print(f"Ошибка загрузки: {e}")
                bot.send_message(chat_id, "❌ Не удалось скачать этот трек. Попробуй выбрать другой.")
            finally:
                if os.path.exists(filename):
                    os.remove(filename)
        else:
            bot.answer_callback_query(call.id, text="Результаты устарели. Введи запрос заново.")

bot.infinity_polling(skip_pending=True)
