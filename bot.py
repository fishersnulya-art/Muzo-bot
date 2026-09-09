import os
import time
import html
import tempfile

import telebot
from telebot import types
import yt_dlp
import imageio_ffmpeg

TOKEN = os.environ.get('BOT_TOKEN')
if not TOKEN:
    raise SystemExit("Не задана переменная окружения BOT_TOKEN")

# parse_mode="HTML" по умолчанию для всех сообщений
bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
user_data = {}

MAX_TELEGRAM_FILE_MB = 49  # лимит обычного Bot API на отправку файлов

# Путь к файлу cookies (экспортированному из браузера с залогиненным YouTube).
# Без него YouTube на IP хостингов почти всегда отвечает
# "Sign in to confirm you're not a bot" — см. README/инструкцию в чате.
COOKIES_FILE = os.environ.get('YOUTUBE_COOKIES_FILE', 'cookies.txt')
if not os.path.exists(COOKIES_FILE):
    COOKIES_FILE = None
    print("⚠️ cookies.txt не найден — запросы к YouTube могут блокироваться (429 / bot-check).")


def base_ydl_opts(extra: dict) -> dict:
    """Общие настройки yt-dlp: cookies + лёгкий троттлинг против 429."""
    opts = {
        'quiet': True,
        'geo_bypass': True,
        'extractor_args': {'youtube': {'player_client': ['ios', 'mweb', 'android']}},
        'sleep_interval_requests': 1,
        'retries': 3,
    }
    if COOKIES_FILE:
        opts['cookiefile'] = COOKIES_FILE
    opts.update(extra)
    return opts


def esc(text: str) -> str:
    """Экранирование текста для HTML parse_mode — защищает от падения бота,
    если в имени пользователя или в поисковом запросе есть символы < > &"""
    return html.escape(text or "")


def get_main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(
        types.KeyboardButton("🔥 Популярные треки & Ремиксы"),
        types.KeyboardButton("❓ Помощь"),
    )
    return markup


@bot.message_handler(commands=['start'])
def start_cmd(message):
    name = esc(message.from_user.first_name)
    welcome_text = (
        f"👋 Привет, <b>{name}</b>!\n\n"
        "🎵 Я музыкальный бот. Ищу любые полные версии треков, ремиксы и новинки "
        "прямо в плеер Telegram.\n\n"
        "🔍 <b>Напиши название песни, исполнителя или ремикса:</b>"
    )
    bot.send_message(message.chat.id, welcome_text, reply_markup=get_main_keyboard())


@bot.message_handler(commands=['help'])
@bot.message_handler(func=lambda m: m.text == "❓ Помощь")
def help_cmd(message):
    help_text = (
        "📌 <b>Как пользоваться ботом:</b>\n\n"
        "1. Отправь название трека или артиста (например: <i>Miyagi ремикс</i> "
        "или <i>Каспийский груз</i>).\n"
        "2. Выбери вариант из списка.\n"
        "3. Используй страницы ⬅️ / ➡️, если результатов много.\n"
        "4. Получи полную песню в плеере Telegram!"
    )
    bot.send_message(message.chat.id, help_text)


@bot.message_handler(commands=['top'])
@bot.message_handler(func=lambda m: m.text == "🔥 Популярные треки & Ремиксы")
def top_music(message):
    search_music_query(message, "русские хиты ремиксы топ", is_top=True)


@bot.message_handler(func=lambda message: True)
def handle_text_search(message):
    search_music_query(message, message.text)


def search_music_query(message, query, is_top=False):
    safe_query = esc(query)
    status_text = (
        "🔥 Подбираю топ-хиты и ремиксы..."
        if is_top else f"🔎 Ищу полные треки: <b>{safe_query}</b>..."
    )

    try:
        status_msg = bot.reply_to(message, status_text)
    except Exception as e:
        print(f"Не удалось отправить статус: {e}")
        return

    try:
        ydl_opts = base_ydl_opts({
            'extract_flat': 'in_playlist',
            'default_search': 'ytsearch12',
        })

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            search_result = ydl.extract_info(f"ytsearch12:{query}", download=False) or {}
            entries = [e for e in search_result.get('entries', []) if e]

        if not entries:
            bot.edit_message_text(
                chat_id=message.chat.id, message_id=status_msg.message_id,
                text="❌ Ничего не найдено. Попробуй уточнить запрос."
            )
            return

        tracks = [
            {
                'id': entry.get('id'),
                'title': entry.get('title') or 'Без названия',
                'duration': entry.get('duration') or 0,
            }
            for entry in entries
        ]

        user_data[message.chat.id] = {'tracks': tracks, 'page': 0}
        cleanup_old_sessions()
        send_page(message.chat.id, status_msg.message_id)

    except Exception as e:
        print(f"Ошибка поиска: {e}")
        try:
            bot.edit_message_text(
                chat_id=message.chat.id, message_id=status_msg.message_id,
                text="❌ Произошла ошибка при поиске. Попробуй еще раз."
            )
        except Exception:
            pass


def cleanup_old_sessions(limit=500):
    """Защита от бесконечного роста user_data в памяти при долгой работе бота."""
    if len(user_data) > limit:
        for chat_id in list(user_data.keys())[:-limit]:
            user_data.pop(chat_id, None)


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
        title = track['title']
        title = title[:45] + '...' if len(title) > 45 else title
        keyboard.add(types.InlineKeyboardButton(text=f"🎵 {title}", callback_data=f"play_{global_idx}"))

    nav_buttons = []
    if page > 0:
        nav_buttons.append(types.InlineKeyboardButton("⬅️ Назад", callback_data="page_prev"))

    total_pages = (len(tracks) + per_page - 1) // per_page
    nav_buttons.append(types.InlineKeyboardButton(f"📄 {page + 1}/{total_pages}", callback_data="page_num"))

    if end_idx < len(tracks):
        nav_buttons.append(types.InlineKeyboardButton("Вперед ➡️", callback_data="page_next"))

    keyboard.row(*nav_buttons)
    bot.edit_message_text(
        chat_id=chat_id, message_id=message_id,
        text="👇 <b>Выбери нужный трек из списка:</b>", reply_markup=keyboard
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

    elif call.data == "page_next":
        if data:
            data['page'] += 1
            send_page(chat_id, call.message.message_id)
        bot.answer_callback_query(call.id)

    elif call.data == "page_num":
        bot.answer_callback_query(call.id, text="Используй стрелки для переключения страниц")

    elif call.data.startswith("play_"):
        handle_play(call, chat_id, data)

    else:
        bot.answer_callback_query(call.id)


def handle_play(call, chat_id, data):
    track_idx = int(call.data.split("_")[1])

    if not data or track_idx >= len(data['tracks']):
        bot.answer_callback_query(call.id, text="Результаты устарели. Введи запрос заново.")
        return

    track = data['tracks'][track_idx]
    video_id = track['id']

    bot.answer_callback_query(call.id, text="📥 Скачиваю полную версию трека...")
    bot.send_chat_action(chat_id, 'upload_document')

    # Используем временную папку — исключает конфликты имён файлов
    # и гарантированно чистит диск после отправки
    with tempfile.TemporaryDirectory() as tmpdir:
        outtmpl = os.path.join(tmpdir, "audio.%(ext)s")
        ydl_opts = base_ydl_opts({
            'format': 'bestaudio/best',
            'outtmpl': outtmpl,
            'ffmpeg_location': FFMPEG_PATH,
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
            'noplaylist': True,
        })

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([f"https://www.youtube.com/watch?v={video_id}"])

            files = [f for f in os.listdir(tmpdir) if f.lower().endswith('.mp3')]
            if not files:
                raise RuntimeError("Файл не сконвертировался в mp3")

            filepath = os.path.join(tmpdir, files[0])
            size_mb = os.path.getsize(filepath) / (1024 * 1024)

            if size_mb > MAX_TELEGRAM_FILE_MB:
                bot.send_message(chat_id, "❌ Трек слишком большой (>49 МБ) для отправки через Telegram.")
                return

            with open(filepath, 'rb') as audio_file:
                bot.send_audio(
                    chat_id=chat_id,
                    audio=audio_file,
                    title=track['title'][:64],
                    performer="MuzoBot",
                    duration=track['duration'],
                )

        except Exception as e:
            print(f"Ошибка загрузки: {e}")
            bot.send_message(chat_id, "❌ Не удалось скачать этот трек. Попробуй выбрать другой.")


if __name__ == '__main__':
    print("Бот запущен...")
    while True:
        try:
            bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=30)
        except Exception as e:
            print(f"Ошибка в polling: {e}")
            time.sleep(3)
