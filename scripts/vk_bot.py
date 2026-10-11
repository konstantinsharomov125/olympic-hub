import json
import os
import re
import random
import logging
from vk_api import VkApi
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.utils import get_random_id

# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Токен сообщества VK (укажите ваш токен или переменную окружения)
VK_TOKEN = os.getenv("VK_GROUP_TOKEN", "vk1.a.OAoAC9DyPKatidruuufqJzHasG_AL_pPUfiP_dtHAQeVn9CZArgQ3kBvJD_SVrRuquFJZVaOhs2_SMOplPKiE1xHEVS2KY3WosPz5ITOI0dp1y6Lx8DCHFmx5er4A5AkvJGMjPiwL72o2o3cnOFsuIJS5hyemskeNPGJljMeF0mWyFUvN-ALsrxIknfc94kyF1Ip7m2xvVEA7rK5c5wkyw")

# Поиск базы данных web_data.json
DATA_PATHS = [
    "generated/web_data.json",
    "data/web_data.json",
    "web_data.json"
]

def load_database():
    for path in DATA_PATHS:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    items = data if isinstance(data, list) else data.get("items", [])
                    logging.info(f"Загружена база данных из {path}: {len(items)} записей.")
                    return items
            except Exception as e:
                logging.error(f"Ошибка чтения {path}: {e}")
    logging.warning("Файл web_data.json не найден!")
    return []

database = load_database()

def search_articles(query, limit=3):
    """Поиск статей по названию, авторам или аннотации."""
    query_lower = query.lower().strip()
    results = []
    
    for item in database:
        title = str(item.get("title_original") or item.get("title") or "").lower()
        authors = str(item.get("authors") or item.get("author") or "").lower()
        summary = str(item.get("summary_ru") or item.get("abstract") or "").lower()
        category = str(item.get("category") or "").lower()
        
        if (query_lower in title) or (query_lower in authors) or (query_lower in summary) or (query_lower in category):
            results.append(item)
            if len(results) >= limit:
                break
                
    return results

def format_article_message(item):
    """Форматирование карточки статьи для VK."""
    title = item.get("title_original") or item.get("title") or "Без названия"
    authors = item.get("authors") or "Автор не указан"
    year = item.get("year", "2026")
    category = item.get("category", "Олимпизм")
    summary = item.get("summary_ru") or item.get("abstract") or "Аннотация отсутствует."
    url = item.get("url") or "https://konstantinsharotov125.github.io/"
    
    if len(summary) > 250:
        summary = summary[:247] + "..."
        
    msg = (
        f"📖 *{title}*\n"
        f"👤 *Авторы:* {authors} ({year})\n"
        f"🏷 *Категория:* {category}\n\n"
        f"📌 *Аннотация:* {summary}\n\n"
        f"🔗 *Ссылка:* {url}"
    )
    return msg

def handle_message(user_text):
    text = user_text.strip().lower()
    
    # Приветствие и справка
    if text in ["начало", "старт", "start", "помощь", "help", "меню"]:
        return (
            "🏛 *Добро пожаловать в Олимпийский исследовательский бот!*\n\n"
            "Я могу помочь найти научные публикации по олимпийскому движению.\n\n"
            "📌 *Команды:*\n"
            "• `поиск <запрос>` — найти статьи по теме, автору или слову\n"
            "• `статистика` — общие данные базы исследований\n"
            "• `рандом` — случайно случайное исследование\n"
            "• `портал` — ссылка на веб-версию портала"
        )

    # Поисковый запрос
    if text.startswith("поиск ") or text.startswith("найти "):
        query = user_text.split(" ", 1)[1]
        results = search_articles(query)
        
        if not results:
            return f"🔍 По запросу «{query}» ничего не найдено. Попробуйте сформулировать иначе."
            
        response = [f"🔎 *Результаты поиска по запросу «{query}»:*\n"]
        for item in results:
            response.append(format_article_message(item))
            
        return "\n\n──────────────\n\n".join(response)

    # Статистика базы
    if text == "статистика":
        total = len(database)
        categories = {}
        for item in database:
            cat = item.get("category", "Другое")
            categories[cat] = categories.get(cat, 0) + 1
            
        top_cat = sorted(categories.items(), key=lambda x: x[1], reverse=True)[:3]
        top_str = "\n".join([f"• {k}: {v}" for k, v in top_cat])
        
        return (
            f"📊 *Статистика Олимпийского исследовательского портала:*\n\n"
            f"📚 Всего исследований в базе: *{total}*\n\n"
            f"🏆 *Топ категорий:*\n{top_str}\n\n"
            f"🌐 Веб-портал: https://konstantinsharotov125.github.io/"
        )

    # Случайная статья
    if text in ["рандом", "случайная", "случайное"]:
        if not database:
            return "База данных временно недоступна."
        item = random.choice(database)
        return "🎲 *Случайное исследование из базы:*\n\n" + format_article_message(item)

    # Ссылка на портал
    if text == "портал":
        return "🌐 Наш исследовательский портал доступен по ссылке:\nhttps://konstantinsharotov125.github.io/"

    # Если неизвестная команда — пробуем выполнить поиск по тексту
    results = search_articles(user_text, limit=2)
    if results:
        response = [f"🔎 *Найдены публикации по вашей фразе «{user_text}»:*\n"]
        for item in results:
            response.append(format_article_message(item))
        return "\n\n──────────────\n\n".join(response)

    return "Напишите `поиск <слово>` для поиска исследований или `помощь` для списка команд."

def main():
    if VK_TOKEN == "YOUR_VK_GROUP_TOKEN_HERE":
        logging.error("Укажите VK_GROUP_TOKEN в файле или через переменную окружения!")
        return

    vk_session = VkApi(token=VK_TOKEN)
    vk = vk_session.get_api()
    longpoll = VkLongPoll(vk_session)
    
    logging.info("🤖 Бот успешно запущен и готов обрабатывать сообщения ВКонтакте...")

    for event in longpoll.listen():
        if event.type == VkEventType.MESSAGE_NEW and event.to_me:
            user_text = event.text
            user_id = event.user_id
            
            reply = handle_message(user_text)
            
            try:
                vk.messages.send(
                    user_id=user_id,
                    message=reply,
                    random_id=get_random_id()
                )
            except Exception as e:
                logging.error(f"Ошибка отправки сообщения: {e}")

if __name__ == "__main__":
    main()