чат."
    )

@bot.message_handler(func=lambda message: True)
def download_and_send_audio(message):
    query = message.text
    status_msg = bot.reply_to(message, f"🔎 Ищу и скачиваю: *{query}*...", parse_mode="Markdown")

    filename = f"song_{message.chat.id}.mp3"

    try:
        # Запрос к открытому API поиска аудио
        encoded_query = urllib.parse.quote(query)
        api_url = f"https://api.vkmusic.ru/search?q={encoded_query}"
        
        # Настройка заголовка запроса
        req = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
        
        # Загрузка прямой аудиоссылки
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            
        if data and len(data) > 0:
            track = data[0]
            audio_url = track.get('url')
            title = track.get('title', query)
            performer = track.get('artist', 'MuzoBot')

            # Скачивание MP3 файла напрямую в память
            urllib.request.urlretrieve(audio_url, filename)

            # Отправка MP3 файла в чат
            with open(filename, 'rb') as audio_file:
                bot.send_audio(
                    chat_id=message.chat.id,
                    audio=audio_file,
                    title=title,
                    performer=performer,
                    reply_to_message_id=message.message_id
                )
            bot.delete_message(chat_id=message.chat.id, message_id=status_msg.message_id)
        else:
            raise Exception("Песня не найдена")

    except Exception as e:
        print(f"Ошибка поиска: {e}")
        # Запасной метод скачивания через резервное зеркало
        try:
            fallback_url = f"https://music-api.mp3.pm/download?q={urllib.parse.quote(query)}"
            bot.send_audio(
                chat_id=message.chat.id,
                audio=fallback_url,
                title=query,
                performer="MuzoBot",
                reply_to_message_id=message.message_id
            )
            bot.delete_message(chat_id=message.chat.id, message_id=status_msg.message_id)
        except Exception as fallback_error:
            print(f"Ошибка запасного метода: {fallback_error}")
            bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=status_msg.message_id,
                
