"""Работа с аннотациями: очистка псевдотекстов и честные статусы.

Каталог не должен выдавать сгенерированный текст за авторскую аннотацию.
Модуль распознаёт шаблонные заглушки, удаляет их и проставляет статус,
по которому интерфейс показывает понятное сообщение.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

from olympic_hub_core import clean

#: Статусы аннотации, которые понимает интерфейс.
ABS_PRESENT = "present"        # есть настоящая аннотация из источника
ABS_NONE = "missing"           # аннотации в источнике нет
ABS_SYNTHETIC = "synthetic"    # была заглушка, удалена
ABS_AI = "ai_summary"          # автоматическое резюме, не авторский текст

#: Сообщение для интерфейса, когда аннотации нет.
MISSING_MESSAGE = "Аннотация не найдена в источнике"

#: Шаблоны, по которым распознаются выдуманные аннотации.
FAKE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^\s*научное\s+исследование\s+по\s+теме", re.I),
    re.compile(r"^\s*данн\w+\s+(?:статья|работа|исследование)\s+посвящен", re.I),
    re.compile(r"^\s*(?:this|the)\s+(?:study|paper|article)\s+(?:is\s+)?(?:devoted|dedicated)\s+to\s+(?:the\s+)?(?:study|topic)\s+of\s+olymp", re.I),
    re.compile(r"^\s*в\s+данной\s+работе\s+рассматривается\s+тема\s+олимп", re.I),
    re.compile(r"^\s*аннотация\s+(?:к\s+)?(?:работе|статье)\s+по\s+теме", re.I),
    re.compile(r"^\s*статья\s+посвящена\s+олимпийской\s+тематике", re.I),
)

#: Тексты-заглушки, которые встречались в данных.
PLACEHOLDERS: frozenset[str] = frozenset(
    {
        "",
        "нет",
        "нет данных",
        "отсутствует",
        "аннотация отсутствует",
        "аннотация отсутствует.",
        "аннотация временно отсутствует в первоисточнике.",
        "аннотация доступна по ссылке на оригинал",
        "n/a",
        "na",
        "none",
        "null",
        "-",
        "—",
    }
)


def is_fake_abstract(text: Any) -> bool:
    """True, если текст является сгенерированной заглушкой."""
    value = clean(text)
    if not value:
        return False
    lowered = value.lower()
    if lowered in PLACEHOLDERS:
        return False
    return any(pattern.search(value) for pattern in FAKE_PATTERNS)


def is_placeholder(text: Any) -> bool:
    return clean(text).lower() in PLACEHOLDERS


def looks_like_translation(original: Any, translated: Any) -> bool:
    """Перевод не должен совпадать с оригиналом побайтово."""
    a, b = clean(original), clean(translated)
    return bool(a and b and a != b)


def sanitize_abstract_fields(record: Mapping[str, Any]) -> dict[str, Any]:
    """Приводит поля аннотации к честному виду.

    * ``abstract_original`` — настоящий текст из источника;
    * ``abstract_ru`` — перевод, только если он действительно отличается;
    * ``abstract_status`` — статус для интерфейса.
    """
    out = dict(record)

    original = clean(
        out.get("abstract_original")
        or out.get("summary_original")
        or out.get("summary")
        or out.get("abstract")
    )
    translated = clean(out.get("abstract_ru") or out.get("summary_ru"))
    removed_fake = False

    if original and is_fake_abstract(original):
        original = ""
        removed_fake = True
    if translated and is_fake_abstract(translated):
        translated = ""
        removed_fake = True
    if is_placeholder(original):
        original = ""
    if is_placeholder(translated):
        translated = ""

    # Перевод, идентичный оригиналу, переводом не является.
    if translated and original and translated == original:
        translated = ""

    out["abstract_original"] = original
    out["abstract_ru"] = translated
    out["abstract_removed_fake"] = removed_fake

    if original:
        out["abstract_status"] = ABS_PRESENT
    else:
        out["abstract_status"] = ABS_SYNTHETIC if removed_fake else ABS_NONE
    out["abstract_display"] = translated or original or MISSING_MESSAGE
    return out


def count_fake_abstracts(records: Any) -> int:
    """Считает записи с фиктивной аннотацией в оригинале или переводе."""
    total = 0
    for record in records:
        candidate = clean(
            record.get("abstract_original")
            or record.get("summary_original")
            or record.get("summary")
            or record.get("abstract")
        )
        translated = clean(record.get("abstract_ru") or record.get("summary_ru"))
        if (candidate and is_fake_abstract(candidate)) or (translated and is_fake_abstract(translated)):
            total += 1
    return total
