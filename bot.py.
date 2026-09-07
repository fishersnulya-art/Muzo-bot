import os
import telebot
from telebot import types

# Сервер сам подставит токен из настроек Render
TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start_cmd(message):
    bot.reply_to(
        message, 
        "Привет! Отправь мне название песни или исполнителя, и я найду варианты для прослушивания."
    )

@bot.message_handler(content_types=['text'])
def search_music(message):
    query = message.text.replace(' ', '+')
    
    # Формирование ссылок для поиска
    yt_music_url = f"https://music.youtube.com/search?q={query}"
    ya_music_url = f"https://music.yandex.ru/search?text={query}"
    
    markup = types.InlineKeyboardMarkup()
    btn1 = types.InlineKeyboardButton("Слушать на YouTube Music", url=yt_music_url)
    btn2 = types.InlineKeyboardButton("Искать в Яндекс Музыке", url=ya_music_url)
    markup.add(btn1)
    markup.add(btn2)
    
    bot.send_message(
        message.chat.id, 
        f"🎵 Результаты поиска по запросу: **{message.text}**", 
        parse_mode="Markdown", 
        reply_markup=markup
    )

if __name__ == '__main__':
    bot.infinity_polling()
