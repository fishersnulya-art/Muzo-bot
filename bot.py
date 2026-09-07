import os
import requests
import telebot
from telebot import types

TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(TOKEN)

# Временное хранилище найденных ссылок на аудио
user_search_results = {}

@bot.message_handler(commands=['start'])
def start_cmd(message):
    bot.reply_to(
        message, 
        "Привет! Напиши мне название песни или исполнителя, и я покажу варианты для скачивания."
    )

@bot.message_handler(func=lambda message: True)
def search_music(message):
    query = message.text
    status_msg = bot.reply_to(message, f"🔎 Ищу варианты по запросу: *{query}*...", parse_mode="Markdown")

    try:
        # Запрос к музыкальной базе
        search_url = f"https://itunes.apple.com/search?term={requests.utils.quote(query)}&media=music&limit=5"
        res = requests.get(search_url, timeout=10).json()

        results = res.get('results', [])

        if not results:
            bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=status_msg.message_id,
                text="❌ Ничего не найдено. Попробуйте ввести запрос по-другому."
            )
            return

        # Формируем кнопки с найденными треками
        keyboard = types.InlineKeyboardMarkup()
        user_search_results[message.chat.id] = {}

        for index, track in enumerate(results):
            track_id = str(index)
            title = track.get('trackName', 'Без названия')
            artist = track.get('artistName', 'Неизвестный исполнитель')
            preview_url = track.get('previewUrl')

            # Сохраняем данные во временный словарь
            user_search_results[message.chat.id][track_id] = {
                'title': title,
                'artist': artist,
                'url': preview_url
            }

            button_text = f"🎵 {artist} — {title}"
            keyboard.add(types.InlineKeyboardButton(text=button_text, callback_data=f"song_{track_id}"))

        bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=status_msg.message_id,
            text="👇 *Выберите нужный трек из списка:*",
            parse_mode="Markdown",
            reply_markup=keyboard
        )

    except Exception as e:
        print(f"Ошибка поиска: {e}")
        bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=status_msg.message_id,
            text="❌ Произошла ошибка при поиске. Попробуйте ещё раз."
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith('song_'))
def handle_music_choice(call):
    chat_id = call.message.chat.id
    track_id = call.data.split('_')[1]

    # Проверяем, есть ли сохраненный выбор для этого пользователя
    if chat_id in user_search_results and track_id in user_search_results[chat_id]:
        track_data = user_search_results[chat_id][track_id]

        bot.answer_callback_query(call.id, text="Загрузка трека...")
        bot.send_chat_action(chat_id, 'upload_voice')

        try:
            # Отправка MP3-файла напрямую в чат
            bot.send_audio(
                chat_id=chat_id,
                audio=track_data['url'],
                title=track_data['title'],
                performer=track_data['artist']
            )
        except Exception as e:
            print(f"Ошибка отправки файла: {e}")
            bot.send_message(chat_id, "❌ Не удалось отправить аудиофайл. Попробуйте выбрать другой вариант.")
    else:
        bot.answer_callback_query(call.id, text="Результаты поиска устарели. Введите запрос заново.")

bot.infinity_polling()
