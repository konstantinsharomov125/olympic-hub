"""Генератор библиографических ссылок принятого в проекте формата.

Формат (не является подтверждённым соответствием ГОСТ):

    Gogovor A. Contemporary Disease Management in Quebec / A. Gogovor,
    M. Savoie, Y. Moride, M. Krelenbaum, T. Montague // Healthcare
    Quarterly. – 2008. – URL: https://example.org/article
    (дата обращения: 10.11.2026).

Правила: реальные данные вместо заглушек, дата обращения вычисляется
в момент генерации, неизвестные поля опускаются.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Mapping, Sequence

from olympic_hub_core import check_year, clean, doi_url, norm_doi

#: Подписи, которые нельзя показывать как источник.
FORBIDDEN_CONTAINERS = frozenset(
    {
        "научная публикация",
        "научная статья",
        "научное исследование",
        "unknown journal",
        "unknown",
        "n/a",
        "na",
        "none",
        "null",
        "-",
        "—",
        "неизвестно",
        "без названия",
    }
)

_INITIALS_RE = re.compile(r"^[А-ЯЁA-Z](?:\.[А-ЯЁA-Z]?\.?)?$")
_CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")


def is_forbidden_container(value: Any) -> bool:
    return clean(value).lower().strip(" .") in FORBIDDEN_CONTAINERS


def split_authors(raw: Any) -> list[str]:
    """Разбивает строку авторов на отдельные имена."""
    text = clean(raw)
    if not text:
        return []
    if isinstance(raw, (list, tuple)):
        return [clean(x) for x in raw if clean(x)]
    # Точка с запятой надёжнее запятой: «Фамилия, И. О.; Другая, П. К.»
    if ";" in text:
        parts = text.split(";")
    elif re.search(r"[А-ЯЁA-Z][а-яёa-z]+,\s*[А-ЯЁA-Z]\.", text):
        parts = re.split(r",\s*(?=[А-ЯЁA-Z][а-яёa-z]+(?:,|\s|$))", text)
    else:
        parts = text.split(",")
    result = [clean(p).rstrip(".") for p in parts]
    return [p for p in result if p and p.lower() not in {"nr", "n/a", "нет"}]


def _name_parts(entry: str) -> tuple[str, list[str]]:
    """Возвращает (фамилия, инициалы) для одной записи автора."""
    text = clean(entry)
    if not text:
        return "", []

    # Форма «Фамилия И.О.» или «Фамилия И. О.»
    match = re.match(r"^(.+?)\s+((?:[А-ЯЁA-Z]\.\s*){1,3})$", text)
    if match:
        surname = match.group(1).strip()
        initials = re.findall(r"[А-ЯЁA-Z]", match.group(2))
        return surname, initials

    # Форма «И.О. Фамилия»
    match = re.match(r"^((?:[А-ЯЁA-Z]\.\s*){1,3})\s*(.+)$", text)
    if match:
        initials = re.findall(r"[А-ЯЁA-Z]", match.group(1))
        return match.group(2).strip(), initials

    parts = text.split()
    if len(parts) >= 2 and all(_INITIALS_RE.match(p) for p in parts[1:]):
        initials = [p.replace(".", "")[:1] for p in parts[1:]]
        return parts[0], initials

    return text, []


def format_first_author(entry: str) -> str:
    """«Gogovor A.» — фамилия и слитные инициалы без хвостовой точки."""
    surname, initials = _name_parts(entry)
    if not surname:
        return ""
    rendered = surname + (" " + "".join(i[0] + "." for i in initials) if initials else "")
    return rendered.rstrip(".")



def format_other_author(entry: str) -> str:
    """«A. Gogovor» — инициалы перед фамилией."""
    surname, initials = _name_parts(entry)
    if not surname:
        return ""
    if not initials:
        return surname
    return f"{' '.join(i[0] + '.' for i in initials)} {surname}"


def format_access_date(moment: date | datetime | None = None) -> str:
    """Дата обращения в формате ДД.ММ.ГГГГ."""
    current = moment or datetime.now()
    if isinstance(current, datetime):
        current = current.date()
    return current.strftime("%d.%m.%Y")


def _resolve_url(record: Mapping[str, Any]) -> str:
    url = clean(record.get("url"))
    if url.startswith(("http://", "https://")):
        return url
    doi = norm_doi(record.get("doi"))
    return doi_url(doi) if doi else ""


def build_citation(
    record: Mapping[str, Any],
    *,
    moment: date | datetime | None = None,
) -> str:
    """Собирает библиографическую ссылку.

    Неизвестные части опускаются. Если данных почти нет, возвращается
    честная неполная ссылка без вымышленных элементов.
    """
    title = clean(record.get("title_original") or record.get("title"))
    container = clean(record.get("container") or record.get("source"))
    if is_forbidden_container(container):
        container = ""

    authors = split_authors(record.get("authors") or record.get("author"))

    year_verdict = check_year(record.get("year"))
    year = str(year_verdict.year) if year_verdict.status == "ok" else ""

    url = _resolve_url(record)
    access = format_access_date(moment)

    parts: list[str] = []

    # Блок 1: авторы и название.
    if authors:
        first = format_first_author(authors[0])
        rest = [format_other_author(a) for a in authors[1:]]
        rest = [r for r in rest if r]
        if first:
            head = f"{first}. {title}" if title else f"{first}."
            if rest:
                head += " / " + ", ".join(rest)
            parts.append(head)
        elif title:
            parts.append(title)
    elif title:
        parts.append(title)

    # Блок 2: источник публикации (только если известен).
    if container:
        parts.append(f"// {container}")

    # Блок 3: год (только подтверждённый).
    if year:
        parts.append(year)

    # Блок 4: ссылка и дата обращения.
    if url:
        parts.append(f"URL: {url} (дата обращения: {access})")

    if not parts:
        return "Недостаточно данных для формирования ссылки"

    result = parts[0]
    for index, chunk in enumerate(parts[1:], start=1):
        # Перед блоком журнала уже стоит «//», поэтому «. – » не дублируем.
        if chunk.startswith("//"):
            result += " " + chunk
        else:
            result += ". – " + chunk
    return result




def has_forbidden_stub(record: Mapping[str, Any]) -> bool:
    """Проверяет, содержит ли запись запрещённые заглушки."""
    fields: Sequence[Any] = (
        record.get("container"),
        record.get("title_original"),
        record.get("title"),
        record.get("authors"),
    )
    return any(is_forbidden_container(f) for f in fields)
