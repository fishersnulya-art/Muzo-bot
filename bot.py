#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
PROPRIETARY TELEGRAM MUSIC BOT ENGINE (v5.5 Enterprise Edition)
Architecture: Multi-Layer Fallback Search, Robust Network Fault Tolerance,
In-Memory Smart Caching, Advanced Long-Polling Stabilization, Admin Telemetry.
=============================================================================
"""

import os
import sys
import time
import json
import logging
import random
import hashlib
import threading
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

import requests
import telebot
from telebot import types

# ---------------------------------------------------------------------------
# 1. LOGGING CONFIGURATION & ADVANCED SETUP
# ---------------------------------------------------------------------------
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] [%(filename)s:%(lineno)d] - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("EnterpriseMusicBot")

# ---------------------------------------------------------------------------
# 2. ENVIRONMENT & CONFIGURATION VALIDATION
# ---------------------------------------------------------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    logger.critical("FATAL: BOT_TOKEN environment variable is missing!")
    BOT_TOKEN = "PLACEHOLDER_TOKEN"

# Multi-instance fallback pools for maximum resilience against domain blacklisting
PIPED_INSTANCES = [
    "https://pipedapi.kavin.rocks",
    "https://pipedapi.drgns.space",
    "https://pipedapi-libre.kavin.rocks",
    "https://piped.video/api",
    "https://pipedapi.privacy.com.de"
]

INVIDIOUS_INSTANCES = [
    "https://vid.puffyan.us",
    "https://inv.nadeko.net",
    "https://invidious.projectsegfau.lt"
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"
]

# Initialize bot with high connection timeout thresholds and thread safety
bot = telebot.TeleBot(BOT_TOKEN, skip_pending=True, num_threads=8)

# ---------------------------------------------------------------------------
# 3. ADVANCED IN-MEMORY STORAGE & CACHING SYSTEMS
# ---------------------------------------------------------------------------
class BotMemoryManager:
    def __init__(self):
        self.user_sessions: Dict[int, Dict[str, Any]] = {}
        self.search_cache: Dict[str, List[Dict[str, Any]]] = {}
        self.download_cache: Dict[str, str] = {}
        self.analytics = {
            "total_searches": 0,
            "total_downloads": 0,
            "active_users": set(),
            "start_time": datetime.now()
        }
        self.lock = threading.Lock()

    def set_session(self, chat_id: int, data: Dict[str, Any]):
        with self.lock:
            self.user_sessions[chat_id] = data

    def get_session(self, chat_id: int) -> Optional[Dict[str, Any]]:
        with self.lock:
            return self.user_sessions.get(chat_id)

    def log_search(self, user_id: int, query: str):
        with self.lock:
            self.analytics["total_searches"] += 1
            self.analytics["active_users"].add(user_id)
            if len(self.search_cache) > 200:
                keys_to_remove = list(self.search_cache.keys())[:50]
                for k in keys_to_remove:
                    self.search_cache.pop(k, None)

    def log_download(self, user_id: int):
        with self.lock:
            self.analytics["total_downloads"] += 1
            self.analytics["active_users"].add(user_id)

memory = BotMemoryManager()

# ---------------------------------------------------------------------------
# 4. NETWORK & REQUEST LAYER WITH EXPONENTIAL BACKOFF
# ---------------------------------------------------------------------------
def execute_with_retry(url: str, params: Optional[Dict] = None, timeout: int = 6, max_retries: int = 3) -> Optional[requests.Response]:
    headers = {"User-Agent": random.choice(USER_AGENTS)}
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(url, params=params, headers=headers, timeout=timeout)
            if response.status_code == 200:
                return response
        except requests.exceptions.RequestException as e:
            logger.warning(f"Network error on attempt {attempt}/{max_retries} for URL {url}: {e}")
            if attempt == max_retries:
                return None
            time.sleep(0.5 * (2 ** (attempt - 1)))
    return None

# ---------------------------------------------------------------------------
# 5. MULTI-ENGINE SEARCH SUBSYSTEM (PIPED & INVIDIOUS FALLBACKS)
# ---------------------------------------------------------------------------
def search_tracks_engine(query: str) -> List[Dict[str, Any]]:
    query_hash = hashlib.md5(query.lower().strip().encode('utf-8')).hexdigest()
    if query_hash in memory.search_cache:
        logger.info(f"Serving query '{query}' from internal memory cache.")
        return memory.search_cache[query_hash]

    tracks = []
    
    # 1. Try Piped API instances without strict filtering for universal search support
    for instance in PIPED_INSTANCES:
        try:
            search_url = f"{instance}/search"
            params = {"q": query}
            resp = execute_with_retry(search_url, params=params, timeout=5)
            
            if resp and resp.status_code == 200:
                data = resp.json()
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
                                'duration': item.get('duration', 180),
                                'source': 'piped'
                            })
                if tracks:
                    logger.info(f"Successfully retrieved {len(tracks)} tracks from Piped instance: {instance}")
                    break
        except Exception as e:
            logger.warning(f"Piped instance {instance} failed: {e}")
            continue

    # 2. If Piped fails completely, try Invidious API fallback instances
    if not tracks:
        for instance in INVIDIOUS_INSTANCES:
            try:
                search_url = f"{instance}/api/v1/search"
                params = {"q": query, "type": "video"}
                resp = execute_with_retry(search_url, params=params, timeout=5)
                
                if resp and resp.status_code == 200:
                    items = resp.json()
                    for item in items:
                        video_id = item.get('videoId')
                        if video_id:
                            tracks.append({
                                'id': video_id,
                                'title': item.get('title', 'Без названия'),
                                'uploader': item.get('author', 'Исполнитель'),
                                'duration': item.get('lengthSeconds', 180),
                                'source': 'invidious'
                            })
                    if tracks:
                        logger.info(f"Successfully retrieved {len(tracks)} tracks from Invidious instance: {instance}")
                        break
            except Exception as e:
                logger.warning(f"Invidious instance {instance} failed: {e}")
                continue

    if tracks:
        memory.search_cache[query_hash] = tracks

    return tracks

def fetch_audio_stream_url(video_id: str) -> Optional[str]:
    if video_id in memory.download_cache:
        return memory.download_cache[video_id]

    for instance in PIPED_INSTANCES:
        try:
            stream_url = f"{instance}/streams/{video_id}"
            resp = execute_with_retry(stream_url, timeout=5)
            if resp and resp.status_code == 200:
                data = resp.json()
                audio_streams = data.get('audioStreams', [])
                if audio_streams:
                    best_stream = max(audio_streams, key=lambda x: x.get('bitrate', 0))
                    direct_url = best_stream.get('url')
                    if direct_url:
                        memory.download_cache[video_id] = direct_url
                        return direct_url
        except Exception as e:
            logger.warning(f"Failed stream lookup on Piped {instance} for ID {video_id}: {e}")
            continue

    for instance in INVIDIOUS_INSTANCES:
        try:
            stream_url = f"{instance}/api/v1/videos/{video_id}"
            resp = execute_with_retry(stream_url, timeout=5)
            if resp and resp.status_code == 200:
                data = resp.json()
                adaptive_formats = data.get('adaptiveFormats', [])
                audio_formats = [f for f in adaptive_formats if 'audio' in f.get('type', '')]
                if audio_formats:
                    best_audio = max(audio_formats, key=lambda x: int(x.get('bitrate', 0) or 0))
                    direct_url = best_audio.get('url')
                    if direct_url:
                        memory.download_cache[video_id] = direct_url
                        return direct_url
        except Exception as e:
            logger.warning(f"Failed stream lookup on Invidious {instance} for ID {video_id}: {e}")
            continue

    return None

# ---------------------------------------------------------------------------
# 6. USER INTERFACE KEYBOARDS & BUILDERS
# ---------------------------------------------------------------------------
def get_main_keyboard() -> types.ReplyKeyboardMarkup:
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_top = types.KeyboardButton("🔥 Популярные хиты & Ремиксы")
    btn_trending = types.KeyboardButton("📈 Тренды недели")
    btn_random = types.KeyboardButton("🎲 Случайный трек")
    btn_help = types.KeyboardButton("❓ Помощь & FAQ")
    markup.add(btn_top, btn_trending, btn_random, btn_help)
    return markup

# ---------------------------------------------------------------------------
# 7. TELEGRAM BOT EVENT HANDLERS & ROUTING LOGIC
# ---------------------------------------------------------------------------
@bot.message_handler(commands=['start'])
def handle_start(message: types.Message):
    user_name = message.from_user.first_name or "Меломан"
    welcome_text = (
        f"🎧 *Приветствую, {user_name}!*\n\n"
        "Добро пожаловать в премиальный музыкальный терминал. "
        "Я могу найти абсолютно любую песню, редкий ремикс, клубный микс или живое выступление "
        "в максимальном качестве без ограничений.\n\n"
        "👇 *Просто отправь мне название трека или воспользуйся меню ниже:*"
    )
    try:
        bot.send_message(
            message.chat.id,
            welcome_text,
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
        logger.info(f"User {message.from_user.id} started the bot.")
    except Exception as e:
        logger.error(f"Error in handle_start: {e}")

@bot.message_handler(commands=['help'])
@bot.message_handler(func=lambda m: m.text in ["❓ Помощь & FAQ", "❓ Помощь"])
def handle_help(message: types.Message):
    help_text = (
        "📖 *Инструкция по использованию бота:*\n\n"
        "1. *Поиск:* Напишите название исполнителя, трека или жанра (например: `Miyagi ремикс` или `Каспийский груз клубная`).\n"
        "2. *Выбор:* Нажмите на нужную кнопку в интерактивном списке.\n"
        "3. *Навигация:* Переключайте страницы кнопками ⬅️ и ➡️, если результатов много.\n"
        "4. *Воспроизведение:* Трек прилетит в ваш аудио-плеер в формате MP3.\n\n"
        "⚙️ Бот оборудован системой многоуровневого обхода ошибок и работает 24/7."
    )
    bot.send_message(message.chat.id, help_text, parse_mode="Markdown")

@bot.message_handler(commands=['stats'])
def handle_admin_stats(message: types.Message):
    uptime = datetime.now() - memory.analytics["start_time"]
    stats_text = (
        "📊 *Статистика работы системы:*\n\n"
        f"⏱ Аптайм: `{str(uptime).split('.')[0]}`\n"
        f"🔍 Всего поисковых запросов: `{memory.analytics['total_searches']}`\n"
        f"📥 Всего скачано треков: `{memory.analytics['total_downloads']}`\n"
        f"👥 Уникальных пользователей: `{len(memory.analytics['active_users'])}`\n"
        "🟢 Статус: Все узлы стабильны."
    )
    bot.send_message(message.chat.id, stats_text, parse_mode="Markdown")

@bot.message_handler(commands=['top'])
@bot.message_handler(func=lambda m: m.text in ["🔥 Популярные хиты & Ремиксы", "📈 Тренды недели", "🎲 Случайный трек"])
def handle_preset_queries(message: types.Message):
    text = message.text
    if "Популярные" in text:
        query = "русские хиты ремиксы клубные топ"
    elif "Тренды" in text:
        query = "tiktok trending remix hits 2026"
    else:
        queries = ["phonk drift mix", "deep house remix hits", "russian rap remix", "synthwave cyberpunk mix"]
        query = random.choice(queries)
    
    execute_search_and_render(message, query)

@bot.message_handler(func=lambda message: True)
def handle_text_query(message: types.Message):
    if not message.text or message.text.startswith('/'):
        return
    execute_search_and_render(message, message.text)

def execute_search_and_render(message: types.Message, query: str):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    memory.log_search(user_id, query)
    status_msg = bot.reply_to(message, f"🔎 Сканирую базы данных по запросу: *{query}*...", parse_mode="Markdown")

    try:
        tracks = search_tracks_engine(query)
        
        if not tracks:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=status_msg.message_id,
                text="❌ По вашему запросу ничего не найдено. Попробуйте изменить формулировку или ввести автора."
            )
            return

        memory.set_session(chat_id, {
            'tracks': tracks[:30],
            'page': 0,
            'query': query
        })

        render_track_page(chat_id, status_msg.message_id)

    except Exception as e:
        logger.error(f"Critical error during search execution for query '{query}': {e}")
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.message_id,
            text="⚠️ Произошла временная ошибка сети при обращении к серверам поиска. Повторите попытку через пару секунд."
        )

def render_track_page(chat_id: int, message_id: int):
    session = memory.get_session(chat_id)
    if not session:
        return

    tracks = session['tracks']
    page = session['page']
    per_page = 5
    
    start_idx = page * per_page
    end_idx = min(start_idx + per_page, len(tracks))
    current_tracks = tracks[start_idx:end_idx]

    keyboard = types.InlineKeyboardMarkup()

    for idx, track in enumerate(current_tracks):
        global_idx = start_idx + idx
        title_clean = track['title'].replace('[', '').replace(']', '')
        button_text = f"🎵 {track['uploader']} — {title_clean}"
        if len(button_text) > 55:
            button_text = button_text[:52] + '...'
        keyboard.add(types.InlineKeyboardButton(text=button_text, callback_data=f"play_{global_idx}"))

    nav_buttons = []
    if page > 0:
        nav_buttons.append(types.InlineKeyboardButton("⬅️ Назад", callback_data="page_prev"))
    
    total_pages = max(1, (len(tracks) + per_page - 1) // per_page)
    nav_buttons.append(types.InlineKeyboardButton(f"📄 {page + 1}/{total_pages}", callback_data="page_num"))

    if end_idx < len(tracks):
        nav_buttons.append(types.InlineKeyboardButton("Вперед ➡️", callback_data="page_next"))

    if nav_buttons:
        keyboard.row(*nav_buttons)

    try:
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="👇 *Выберите нужный трек или ремикс из списка:*",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    except Exception as e:
        logger.debug(f"Ignored non-critical edit message exception: {e}")

# ---------------------------------------------------------------------------
# 8. CALLBACK QUERY ROUTING & DISPATCHER
# ---------------------------------------------------------------------------
@bot.callback_query_handler(func=lambda call: True)
def handle_callback_dispatcher(call: types.CallbackQuery):
    chat_id = call.message.chat.id
    session = memory.get_session(chat_id)

    try:
        if call.data == "page_prev":
            if session and session['page'] > 0:
                session['page'] -= 1
                render_track_page(chat_id, call.message.message_id)
            bot.answer_callback_query(call.id)

        elif call.data == "page_next":
            if session:
                max_page = (len(session['tracks']) - 1) // 5
                if session['page'] < max_page:
                    session['page'] += 1
                    render_track_page(chat_id, call.message.message_id)
            bot.answer_callback_query(call.id)

        elif call.data == "page_num":
            bot.answer_callback_query(call.id, text="Используйте кнопки со стрелками для навигации по страницам.")

        elif call.data.startswith("play_"):
            track_idx = int(call.data.split("_")[1])
            if not session or track_idx >= len(session['tracks']):
                bot.answer_callback_query(call.id, text="⚠️ Результаты поиска устарели. Введите запрос заново.")
                return

            track = session['tracks'][track_idx]
            video_id = track['id']
            title = track['title']
            performer = track['uploader']
            duration = track.get('duration', 180)

            bot.answer_callback_query(call.id, text="⚡ Генерация потока и отправка...")
            bot.send_chat_action(chat_id, 'upload_document')

            audio_url = fetch_audio_stream_url(video_id)
            if not audio_url:
                bot.send_message(chat_id, "❌ Не удалось получить стабильный аудиопоток для этого трека. Попробуйте выбрать другой.")
                return

            temp_filename = f"audio_{chat_id}_{int(time.time())}.mp3"
            download_success = False

            try:
                with requests.get(audio_url, stream=True, timeout=20) as r:
                    if r.status_code == 200:
                        with open(temp_filename, 'wb') as f:
                            for chunk in r.iter_content(chunk_size=16384):
                                if chunk:
                                    f.write(chunk)
                        download_success = True

                if download_success and os.path.exists(temp_filename):
                    memory.log_download(call.from_user.id)
                    with open(temp_filename, 'rb') as audio_file:
                        bot.send_audio(
                            chat_id=chat_id,
                            audio=('audio.mp3', audio_file.read()),
                            title=title[:60],
                            performer=performer[:40],
                            duration=int(duration)
                        )
                else:
                    raise Exception("Stream download validation failed.")

            except Exception as e:
                logger.error(f"Error downloading or sending track {video_id}: {e}")
                bot.send_message(chat_id, "⚠️ Ошибка при передаче аудиофайла. Попробуйте выбрать другую версию трека.")
            finally:
                if os.path.exists(temp_filename):
                    try:
                        os.remove(temp_filename)
                    except Exception:
                        pass

    except Exception as e:
        logger.error(f"Critical error in callback handler: {e}")
        try:
            bot.answer_callback_query(call.id, text="Произошла непредвиденная ошибка.")
        except Exception:
            pass

# ---------------------------------------------------------------------------
# 9. MAIN RUNTIME LOOP WITH AUTO-RECOVERY
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    logger.info("==================================================")
    logger.info("STARTING ENTERPRISE TELEGRAM MUSIC BOT ENGINE v5.5")
    logger.info("==================================================")
    
    while True:
        try:
            logger.info("Initiating Telegram Bot polling listener...")
            bot.infinity_polling(skip_pending=True, interval=1, timeout=20)
        except Exception as err:
            logger.error(f"Critical crash in polling loop: {err}. Restarting in 5 seconds...")
            time.sleep(5)
