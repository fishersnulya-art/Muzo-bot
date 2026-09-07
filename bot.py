import os
import telebot
from telebot import types

TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start_cmd(message):
    bot.reply_to(
        message, 
        "Привет! Я ищу музыку прямо внутри Telegram.\n\n"
        "Напиши мне имя исполнителя или название песни, и я попробую найти трек!"
    )

@bot.inline_handler(lambda query: len(query.query) > 0)
def query_text(inline_query):
    try:
        # Инлайн-поиск аудиозаписей по названию/исполнителю
        results = [
            types.InlineQueryResultArticle(
                id='1',
                title=f"Искать '{inline_query.query}'",
                description="Нажмите, чтобы отправить запрос на поиск аудио",
                input_message_content=types.InputTextMessageContent(
                    message_text=f"🎵 Ищу песню: {inline_query.query}"
                )
            )
        ]
        bot.answer_inline_query(inline_query.id, results)
    except Exception as e:
        print(e)

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    query = message.text
    bot.reply_to(
        message, 
        f"🔍 Для поиска трека '{query}' прямо внутри Telegram перейдите в любой чат и введите:\n\n"
        f"`@{bot.get_me().username} {query}`\n\n"
        f"*(Убедитесь, что Inline Mode включен в @BotFather)*",
        parse_mode="Markdown"
    )

bot.infinity_polling()
