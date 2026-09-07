import os
import time
import requests
import telebot
from telebot import types

TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(TOKEN, skip_pending=True)

# Временное хранилище результатов для каждого чата
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
        "🎵 Я мультиисточниковый музыкальный бот. Я ищу треки по глобальным каталогам "
        "и отправляю их прямо в плеер Telegram.\n\n"
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
        "1. Отправь имя артиста или трек (например: `Каспийский груз` или `Miyagi`).\n"
        "2. Выбери нужный вариант из интерактивного списка.\n"
        "3. Используй страницы ⬅️ / ➡️ для навигации.\n"
        "4. Получи аудиозапись в стандартном плеере Telegram!"
    )
    bot.send_message(message.chat.id, help_text, parse_mode="Markdown")

@bot.message_handler(commands=['top'])
@bot.message_handler(func=lambda m: m.text == "🔥 Популярные треки")
def top_music(message):
    search_music_query(message, "Global Chart Hits", is_top=True)

@bot.message_handler(func=lambda message: True)
def handle_text_search(message):
    search_music_query(message, message.text)

def search_music_query(message, query, is_top=False):
    status_text = "🔥 Подбираю чарт-хиты..." if is_top else f"🔎 Ищу по всем каталогам: *{query}*..."
    status_msg = bot.reply_to(message, status_text, parse_mode="Markdown")

    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        clean_query = requests.utils.quote(query.strip())
        limit = 15 if is_top else 10

        tracks = []

        # Источник 1: Apple Music Каталог
        itunes_url = f"https://itunes.apple.com/search?term={clean_query}&media=music&limit={limit}"
        res = requests.get(itunes_url, headers=headers, timeout=8).json()
        for item in res.get('results', []):
            preview = item.get('previewUrl')
            if preview:
                tracks.append({
                    'title': item.get('trackName', 'Без названия'),
                    'artist': item.get('artistName', 'Неизвестный исполнитель'),
                    'url': preview,
                    'duration': int(item.get('trackTimeMillis', 30000) / 1000)
                })

        # Источник 2: Jamendo Open Music API (резервный каталог свободной и популярной музыки)
        if len(tracks) < 5:
            jamendo_url = f"https://api.jamendo.com/v3.0/tracks/?client_id=5630a45d&format=json&limit=10&search={clean_query}"
            j_res = requests.get(jamendo_url, headers=headers, timeout=8).json()
            for item in j_res.get('results', []):
                audio = item.get('audio')
                if audio:
                    tracks.append({
                        'title': item.get('name', 'Без названия'),
                        'artist': item.get('artist_name', 'Неизвестный исполнитель'),
                        'url': audio,
                        'duration': int(item.get('duration', 180))
                    })

        if not tracks:
            bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=status_msg.message_id,
                text="❌ По данному запросу ничего не найдено. Попробуй изменить название."
            )
            return

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
        button_text = f"🎵 {track['artist']} — {track['title']}"
        if len(button_text) > 60:
            button_text = button_text[:57] + '...'
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
            
            bot.answer_callback_query(call.id, text="🚀 Загружаю аудио в плеер...")
            bot.send_chat_action(chat_id, 'upload_document')

            temp_filename = f"track_{chat_id}.mp3"

            try:
                # Скачиваем файл на сервер Render для корректного формирования тегов
                audio_bytes = requests.get(track['url'], timeout=15).content
                with open(temp_filename, 'wb') as f:
                    f.write(audio_bytes)

                # Отправка с принудительным указанием имени файла для отображения плеера
                with open(temp_filename, 'rb') as audio_file:
                    bot.send_audio(
                        chat_id=chat_id,
                        audio=('audio.mp3', audio_file.read()),
                        title=track['title'],
                        performer=track['artist'],
                        duration=track['duration']
                    )
            except Exception as e:
                print(f"Ошибка скачивания/отправки: {e}")
                bot.send_message(chat_id, "❌ Не удалось отправить этот аудиофайл. Выберите другой вариант.")
            finally:
                if os.path.exists(temp_filename):
                    os.remove(temp_filename)
        else:
            bot.answer_callback_query(call.id, text="Результаты устарели. Введи запрос заново.")

if __name__ == '__main__':
    print("Мульти-бот запускается... Ожидание освобождения потока...")
    time.sleep(5)
    while True:
        try:
            bot.infinity_polling(skip_pending=True)
        except Exception as e:
            print(f"Ошибка в polling: {e}")
            time.sleep(3)
