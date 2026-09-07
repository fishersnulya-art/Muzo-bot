import os
import requests
import telebot
from telebot import types

TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(TOKEN)

# Временное хранилище результатов поиска для каждого пользователя
user_data = {}

def get_main_keyboard():
    """Создает меню с кнопками под полем ввода"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn_top = types.KeyboardButton("🔥 Популярные треки")
    btn_help = types.KeyboardButton("❓ Помощь")
    markup.add(btn_top, btn_help)
    return markup

@bot.message_handler(commands=['start'])
def start_cmd(message):
    welcome_text = (
        f"👋 Привет, *{message.from_user.first_name}*!\n\n"
        "🎵 Я музыкальный бот. Я умею искать треки и отправлять их "
        "прямо в чат в формате плеера Telegram.\n\n"
        "🔍 *Просто напиши название песни или исполнителя:*"
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
        "1. Отправьте имя артиста или название трека (например: `Miyagi` или `Каспийский груз`).\n"
        "2. Выберите нужный вариант из списка с помощью кнопок.\n"
        "3. Переключайте страницы кнопками ⬅️ / ➡️, если результатов много.\n"
        "4. Нажмите на трек, и я сразу пришлю его в плеере!"
    )
    bot.send_message(message.chat.id, help_text, parse_mode="Markdown")

@bot.message_handler(commands=['top'])
@bot.message_handler(func=lambda m: m.text == "🔥 Популярные треки")
def top_music(message):
    # Поиск популярных мировых и русскоязычных хитов
    search_music_query(message, "Top Hits 2026", is_top=True)

@bot.message_handler(func=lambda message: True)
def handle_text_search(message):
    search_music_query(message, message.text)

def search_music_query(message, query, is_top=False):
    status_text = "🔥 Загружаю топ-хиты..." if is_top else f"🔎 Ищу: *{query}*..."
    status_msg = bot.reply_to(message, status_text, parse_mode="Markdown")

    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        clean_query = requests.utils.quote(query.strip())
        limit = 15 if is_top else 10
        search_url = f"https://itunes.apple.com/search?term={clean_query}&media=music&limit={limit}"
        
        response = requests.get(search_url, headers=headers, timeout=10)
        res = response.json()
        results = res.get('results', [])

        if not results:
            bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=status_msg.message_id,
                text="❌ Ничего не найдено. Попробуйте изменить или уточнить запрос."
            )
            return

        # Сохраняем найденные результаты в память для пагинации
        tracks = []
        for track in results:
            tracks.append({
                'title': track.get('trackName', 'Без названия'),
                'artist': track.get('artistName', 'Неизвестный исполнитель'),
                'url': track.get('previewUrl'),
                'duration': int(track.get('trackTimeMillis', 0) / 1000)
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
            text="❌ Произошла ошибка при поиске. Попробуйте повторить позже."
        )

def send_page(chat_id, message_id):
    """Формирует список треков с пагинацией (по 5 кнопок на страницу)"""
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

    # Добавляем кнопки с треками
    for idx, track in enumerate(current_tracks):
        global_idx = start_idx + idx
        button_text = f"🎵 {track['artist']} — {track['title']}"
        keyboard.add(types.InlineKeyboardButton(text=button_text, callback_data=f"play_{global_idx}"))

    # Пагинационные кнопки ⬅️ / ➡️
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
        text="👇 *Выберите нужный трек из списка:*",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    chat_id = call.message.chat.id
    data = user_data.get(chat_id)

    # Переключение страниц
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

    # Воспроизведение выданного трека
    elif call.data.startswith("play_"):
        track_idx = int(call.data.split("_")[1])

        if data and track_idx < len(data['tracks']):
            track = data['tracks'][track_idx]
            bot.answer_callback_query(call.id, text="🚀 Отправка трека...")
            bot.send_chat_action(chat_id, 'upload_document')

            try:
                bot.send_audio(
                    chat_id=chat_id,
                    audio=track['url'],
                    title=track['title'],
                    performer=track['artist'],
                    duration=track['duration']
                )
            except Exception as e:
                print(f"Ошибка отправки файла: {e}")
                bot.send_message(chat_id, "❌ Ошибка при отправке аудиозаписи.")
        else:
            bot.answer_callback_query(call.id, text="Результаты устарели. Введите запрос заново.")

bot.infinity_polling()
