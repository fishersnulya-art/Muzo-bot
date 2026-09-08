import os
import time
import requests
import telebot
from telebot import types

TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(TOKEN, skip_pending=True)

# Зеркала музыкального API для обхода блокировок
PIPED_INSTANCES = [
    "https://pipedapi.kavin.rocks",
    "https://pipedapi.drgns.space",
    "https://pipedapi-libre.kavin.rocks"
]

user_data = {}

def get_main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn_top = types.KeyboardButton("🔥 Популярное & Ремиксы")
    btn_help = types.KeyboardButton("❓ Помощь")
    markup.add(btn_top, btn_help)
    return markup

@bot.message_handler(commands=['start'])
def start_cmd(message):
    welcome_text = (
        f"👋 Привет, *{message.from_user.first_name}*!\n\n"
        "🎵 Я музыкальный бот. Ищу любые полные версии треков, ремиксы и клубные миксы "
        "мгновенно и без сбоев.\n\n"
        "🔍 *Напиши название песни, исполнителя или ремикса:*"
    )
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown", reply_markup=get_main_keyboard())

@bot.message_handler(commands=['help'])
@bot.message_handler(func=lambda m: m.text == "❓ Помощь")
def help_cmd(message):
    help_text = (
        "📌 *Как пользоваться ботом:*\n\n"
        "1. Напиши в чат название трека или артиста (например: `Каспийский груз ремикс`).\n"
        "2. Выбери нужную песню из интерактивного списка.\n"
        "3. Используй страницы ⬅️ / ➡️ для переключения.\n"
        "4. Трек мгновенно прилетит в твой плеер!"
    )
    bot.send_message(message.chat.id, help_text, parse_mode="Markdown")

@bot.message_handler(commands=['top'])
@bot.message_handler(func=lambda m: m.text == "🔥 Популярное & Ремиксы")
def top_music(message):
    search_music_query(message, "русские хиты ремиксы клубные", is_top=True)

@bot.message_handler(func=lambda message: True)
def handle_text_search(message):
    search_music_query(message, message.text)

def search_music_query(message, query, is_top=False):
    status_text = "🔥 Загружаю горячие треки и ремиксы..." if is_top else f"🔎 Ищу по всей базе: *{query}*..."
    status_msg = bot.reply_to(message, status_text, parse_mode="Markdown")

    tracks = []
    success = False

    for instance in PIPED_INSTANCES:
        try:
            search_url = f"{instance}/search?q={requests.utils.quote(query)}&filter=music_songs"
            response = requests.get(search_url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                items = data.get('items', [])
                
                for item in items:
                    if item.get('type') == 'stream':
                        url_path = item.get('url', '')
                        video_id = url_path.split('v=')[-1] if 'v=' in url_path else ''
                        if video_id:
                            tracks.append({
                                'id': video_id,
                                'title': item.get('title', 'Без названия'),
                                'uploader': item.get('uploaderName', 'Исполнитель'),
                                'duration': item.get('duration', 180)
                            })
                if tracks:
                    success = True
                    break
        except Exception:
            continue

    if not success or not tracks:
        bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=status_msg.message_id,
            text="❌ Ничего не найдено. Попробуйте изменить поисковый запрос."
        )
        return

    user_data[message.chat.id] = {
        'tracks': tracks[:25],
        'page': 0
    }

    send_page(message.chat.id, status_msg.message_id)

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
        button_text = f"🎵 {track['uploader']} — {track['title']}"
        if len(button_text) > 55:
            button_text = button_text[:52] + '...'
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
        text="👇 *Выберите нужный трек или ремикс:*",
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
        bot.answer_callback_query(call.id, text="Используйте стрелки для переключения страниц")
        return

    elif call.data.startswith("play_"):
        track_idx = int(call.data.split("_")[1])

        if data and track_idx < len(data['tracks']):
            track = data['tracks'][track_idx]
            video_id = track['id']
            
            bot.answer_callback_query(call.id, text="⚡ Загружаю полную версию...")
            bot.send_chat_action(chat_id, 'upload_document')

            audio_download_url = None
            
            for instance in PIPED_INSTANCES:
                try:
                    stream_url = f"{instance}/streams/{video_id}"
                    res = requests.get(stream_url, timeout=5)
                    if res.status_code == 200:
                        stream_data = res.json()
                        audio_streams = stream_data.get('audioStreams', [])
                        if audio_streams:
                            audio_download_url = audio_streams[0].get('url')
                            break
                except Exception:
                    continue

            if not audio_download_url:
                bot.send_message(chat_id, "❌ Не удалось получить аудиопоток. Попробуйте другой трек.")
                return

            temp_filename = f"track_{chat_id}.mp3"

            try:
                with requests.get(audio_download_url, stream=True, timeout=15) as r:
                    r.raise_for_status()
                    with open(temp_filename, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)

                with open(temp_filename, 'rb') as audio_file:
                    bot.send_audio(
                        chat_id=chat_id,
                        audio=('audio.mp3', audio_file.read()),
                        title=track['title'],
                        performer=track['uploader'],
                        duration=track['duration']
                    )
            except Exception as e:
                print(f"Ошибка скачивания: {e}")
                bot.send_message(chat_id, "❌ Ошибка при загрузке трека. Попробуйте выбрать другой.")
            finally:
                if os.path.exists(temp_filename):
                    os.remove(temp_filename)
        else:
            bot.answer_callback_query(call.id, text="Результаты устарели. Введите запрос заново.")

if __name__ == '__main__':
    print("Бот запущен...")
    while True:
        try:
            bot.infinity_polling(skip_pending=True)
        except Exception as e:
            print(f"Ошибка в polling: {e}")
            time.sleep(3)
