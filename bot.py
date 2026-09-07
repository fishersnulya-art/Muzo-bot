import os
import time
import requests
import telebot
from telebot import types

TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(TOKEN, skip_pending=True)

# Хранилище сессий пользователей для пагинации
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
        "🎵 Я расширенный музыкальный бот. Я ищу и скачиваю **полные версии треков** "
        "из свободных глобальных каталогов прямо в плеер Telegram.\n\n"
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
        "1. Отправь имя исполнителя или название трека (например: `LOBODA`, `Miyagi` или `Rock`).\n"
        "2. Выбери нужный трек из интерактивного списка.\n"
        "3. Переключай страницы кнопками ⬅️ / ➡️.\n"
        "4. Получай полную песню в стандартном аудиоплеере Telegram!"
    )
    bot.send_message(message.chat.id, help_text, parse_mode="Markdown")

@bot.message_handler(commands=['top'])
@bot.message_handler(func=lambda m: m.text == "🔥 Популярные треки")
def top_music(message):
    search_music_query(message, "Global Hits", is_top=True)

@bot.message_handler(func=lambda message: True)
def handle_text_search(message):
    search_music_query(message, message.text)

def search_music_query(message, query, is_top=False):
    status_text = "🔥 Загружаю топ-чарт полных треков..." if is_top else f"🔎 Ищу полные треки: *{query}*..."
    status_msg = bot.reply_to(message, status_text, parse_mode="Markdown")

    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        clean_query = requests.utils.quote(query.strip())
        tracks = []

        # Источник 1: Jamendo API (дает полноценные треки без ограничений в 30 секунд)
        jamendo_url = f"https://api.jamendo.com/v3.0/tracks/?client_id=5630a45d&format=json&limit=15&search={clean_query}&audioformat=mp32"
        response = requests.get(jamendo_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            for item in data.get('results', []):
                audio_url = item.get('audio')
                if audio_url:
                    tracks.append({
                        'title': item.get('name', 'Без названия'),
                        'artist': item.get('artist_name', 'Неизвестный исполнитель'),
                        'url': audio_url,
                        'duration': int(item.get('duration', 180))
                    })

        # Источник 2: Дополнительный поиск через публичные музыкальные архивы, если первый дал мало результатов
        if len(tracks) < 5:
            archive_url = f"https://archive.org/advancedsearch.php?q=title%3A({clean_query})%20AND%20mediatype%3A(audio)&rows=10&output=json"
            arch_res = requests.get(archive_url, headers=headers, timeout=10).json()
            docs = arch_res.get('response', {}).get('docs', [])
            
            for doc in docs:
                identifier = doc.get('identifier')
                title = doc.get('title', 'Архивный трек')
                creator = doc.get('creator', 'Сборник')
                if identifier:
                    # Формируем прямую ссылку на скачивание полного mp3 файла из архива
                    tracks.append({
                        'title': title if isinstance(title, str) else title[0],
                        'artist': creator if isinstance(creator, str) else creator[0],
                        'url': f"https://archive.org/download/{identifier}/{identifier}_vbr.mp3",
                        'duration': 200
                    })

        if not tracks:
            bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=status_msg.message_id,
                text="❌ По вашему запросу полных треков не найдено. Попробуйте изменить ключевые слова."
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
            text="❌ Произошла ошибка при поиске. Попробуйте еще раз позже."
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
        text="👇 *Выберите нужный трек (полная версия):*",
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
            
            bot.answer_callback_query(call.id, text="📥 Скачиваю полную версию трека...")
            bot.send_chat_action(chat_id, 'upload_document')

            temp_filename = f"full_track_{chat_id}.mp3"

            try:
                # Загружаем полный файл на сервер Render
                file_response = requests.get(track['url'], timeout=20)
                if file_response.status_code == 200:
                    with open(temp_filename, 'wb') as f:
                        f.write(file_response.content)

                    # Отправляем в Telegram с принудительным расширением mp3 для отображения плеера
                    with open(temp_filename, 'rb') as audio_file:
                        bot.send_audio(
                            chat_id=chat_id,
                            audio=('audio.mp3', audio_file.read()),
                            title=track['title'],
                            performer=track['artist'],
                            duration=track['duration']
                        )
                else:
                    raise Exception("Не удалось скачать поток")

            except Exception as e:
                print(f"Ошибка загрузки полного файла: {e}")
                bot.send_message(chat_id, "❌ Не удалось загрузить этот трек. Попробуйте выбрать другой.")
            finally:
                if os.path.exists(temp_filename):
                    os.remove(temp_filename)
        else:
            bot.answer_callback_query(call.id, text="Результаты устарели. Введите запрос заново.")

if __name__ == '__main__':
    print("Бот запускается... Ожидание освобождения потока...")
    time.sleep(5)
    while True:
        try:
            bot.infinity_polling(skip_pending=True)
        except Exception as e:
            print(f"Ошибка в polling: {e}")
            time.sleep(3)
