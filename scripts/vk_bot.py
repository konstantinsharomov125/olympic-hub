"""Бот сообщества ВКонтакте для Олимпийского исследовательского портала.

Требования безопасности:
  * токен читается ТОЛЬКО из переменной окружения ``VK_GROUP_TOKEN``;
  * встроенных значений по умолчанию нет;
  * при отсутствии токена бот завершается с понятным сообщением
    и не пытается авторизоваться;
  * значение токена никогда не пишется в логи.

Для сообщества используется ``VkBotLongPoll`` и события ``MessageNew``,
то есть корректный механизм бота сообщества, а не пользовательский Long Poll.

Запуск (локально):
    set VK_GROUP_TOKEN=...        (Windows PowerShell: $env:VK_GROUP_TOKEN="...")
    python scripts/vk_bot.py

В GitHub Actions бот не запускается: для Long Poll нужен постоянно
работающий процесс, а еженедельный job для этого не предназначен.
"""

from __future__ import annotations

import logging
import os
import random
import sys
from pathlib import Path

TOKEN_ENV_VAR = "VK_GROUP_TOKEN"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger("vk_bot")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DATA_PATHS = (
    ROOT / "public" / "web_data.json",
    ROOT / "generated" / "web_data.json",
    ROOT / "web_data.json",
)


def read_token() -> str | None:
    """Возвращает токен из окружения или None. Значение не логируется."""
    token = (os.getenv(TOKEN_ENV_VAR) or "").strip()
    return token or None


def load_database() -> list[dict]:
    """Читает публичный каталог из единого контракта {metadata, data}."""
    import json

    for path in DATA_PATHS:
        if not path.exists():
            continue
        try:
            with open(path, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
            if isinstance(payload, dict) and isinstance(payload.get("data"), list):
                records = payload["data"]
            elif isinstance(payload, list):
                records = payload
            else:
                log.warning("Файл %s имеет неожиданный формат", path)
                continue
            public = [r for r in records if r.get("relevance_status", "accepted") == "accepted"]
            log.info("Загружено записей из %s: %s", path.name, len(public))
            return public
        except (OSError, ValueError) as exc:
            log.error("Не удалось прочитать %s: %s", path.name, exc)
    log.warning("Файл данных не найден")
    return []


PORTAL_URL = "https://konstantinsharotov125.github.io/"


def search_articles(database: list[dict], query: str, limit: int = 3) -> list[dict]:
    needle = query.lower().strip()
    if not needle:
        return []
    results = []
    for item in database:
        haystack = " ".join(
            str(item.get(key) or "").lower()
            for key in ("title_original", "authors", "abstract_ru", "abstract_original", "category")
        )
        if needle in haystack:
            results.append(item)
            if len(results) >= limit:
                break
    return results


def format_article(item: dict) -> str:
    from olympic_abstracts import MISSING_MESSAGE

    title = item.get("title_original") or "Без названия"
    authors = item.get("authors") or "Автор не указан"
    year = item.get("year") or "год не указан"
    category = item.get("category") or "Без категории"
    summary = item.get("abstract_display") or item.get("abstract_ru") or MISSING_MESSAGE
    if len(summary) > 250:
        summary = summary[:247] + "..."
    url = item.get("url") or ""

    lines = [
        f"📖 {title}",
        f"👤 Авторы: {authors} ({year})",
        f"🏷 Категория: {category}",
        "",
        f"📌 {summary}",
    ]
    if url:
        lines += ["", f"🔗 {url}"]
    return "\n".join(lines)


HELP_TEXT = (
    "🏛 Олимпийский исследовательский бот\n\n"
    "Команды:\n"
    "• поиск <запрос> — найти публикации\n"
    "• статистика — сведения о каталоге\n"
    "• рандом — случайная публикация\n"
    "• портал — ссылка на сайт"
)


def handle_message(database: list[dict], text: str) -> str:
    from olympic_abstracts import MISSING_MESSAGE  # noqa: F401  (единая терминология)

    value = (text or "").strip()
    lowered = value.lower()

    if lowered in {"начало", "старт", "start", "помощь", "help", "меню"}:
        return HELP_TEXT

    for prefix in ("поиск ", "найти "):
        if lowered.startswith(prefix):
            query = value[len(prefix):].strip()
            results = search_articles(database, query)
            if not results:
                return f"🔍 По запросу «{query}» ничего не найдено."
            blocks = [f"🔎 Найдено по запросу «{query}»:"]
            blocks += [format_article(item) for item in results]
            return "\n\n──────────────\n\n".join(blocks)

    if lowered == "статистика":
        categories: dict[str, int] = {}
        for item in database:
            key = item.get("category") or "Без категории"
            categories[key] = categories.get(key, 0) + 1
        top = sorted(categories.items(), key=lambda kv: kv[1], reverse=True)[:3]
        top_text = "\n".join(f"• {name}: {count}" for name, count in top) or "• нет данных"
        return (
            "📊 Статистика каталога\n\n"
            f"📚 Публикаций в каталоге: {len(database)}\n\n"
            f"🏆 Основные направления:\n{top_text}\n\n"
            f"🌐 {PORTAL_URL}"
        )

    if lowered in {"рандом", "случайная", "случайное"}:
        if not database:
            return "Каталог временно недоступен."
        return "🎲 Случайная публикация:\n\n" + format_article(random.choice(database))

    if lowered == "портал":
        return f"🌐 Портал доступен по ссылке:\n{PORTAL_URL}"

    results = search_articles(database, value, limit=2)
    if results:
        blocks = [f"🔎 Найдено по фразе «{value}»:"]
        blocks += [format_article(item) for item in results]
        return "\n\n──────────────\n\n".join(blocks)

    return "Напишите «поиск <слово>» или «помощь» для списка команд."


def main() -> int:
    token = read_token()
    if not token:
        log.error(
            "Переменная окружения %s не задана. Бот не будет запущен. "
            "Задайте токен сообщества в настройках окружения.",
            TOKEN_ENV_VAR,
        )
        return 1

    try:
        from vk_api import VkApi
        from vk_api.bot_longpoll import VkBotEventType, VkBotLongPoll
        from vk_api.utils import get_random_id
    except ImportError:
        log.error(
            "Библиотека vk_api не установлена. Установите зависимости: "
            "pip install -r requirements.txt"
        )
        return 1

    group_id = (os.getenv("VK_GROUP_ID") or "").strip()
    if not group_id:
        log.error(
            "Переменная окружения VK_GROUP_ID не задана. "
            "Для бота сообщества нужен числовой ID группы."
        )
        return 1

    database = load_database()

    vk_session = VkApi(token=token)
    longpoll = VkBotLongPoll(vk_session, int(group_id))
    api = vk_session.get_api()

    log.info("Бот сообщества запущен, Long Poll ожидает сообщения")

    for event in longpoll.listen():
        if event.type != VkBotEventType.MESSAGE_NEW:
            continue

        message = event.object.message
        text = message.get("text", "")
        peer_id = message.get("peer_id")
        if not peer_id:
            continue

        try:
            answer = handle_message(database, text)
            api.messages.send(peer_id=peer_id, message=answer, random_id=get_random_id())
        except Exception as exc:  # noqa: BLE001
            log.error("Ошибка при обработке сообщения: %s", type(exc).__name__)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

