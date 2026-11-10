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

from olympic_hub_core import check_year, clean, doi_url, is_doi_like, norm_doi

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

_INITIALS_RE = re.compile(r"^[А-ЯЁA-Z](?:\.?[А-ЯЁA-Z]?\.?)?$")
_CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")
#: Слова, которые не являются фамилией автора.
_NOT_AUTHOR = frozenset(
    {"nr", "n/a", "na", "нет", "автор не указан", "неизвестен", "unknown", "anon", "anonymous"}
)


def is_forbidden_container(value: Any) -> bool:
    return clean(value).lower().strip(" .") in FORBIDDEN_CONTAINERS


def has_author(raw: Any) -> bool:
    """Есть ли в записи реальный автор (заглушки не считаются)."""
    for entry in split_authors(raw):
        if _name_parts(entry)[0]:
            return True
    return False


def _split_two_authors(text: str) -> list[str]:
    """«Иванов И. И. Петров П. П.» → два автора (без запятых между ними)."""
    pattern = re.compile(
        r"(.+?[А-ЯЁA-Z][а-яёa-z-]+(?:\s+(?:[А-ЯЁA-Z]\.){1,3})?)"
        r"(?=\s+[А-ЯЁA-Z][а-яёa-z-]+(?:\s+(?:[А-ЯЁA-Z]\.){1,3})?\s*$)"
    )
    found = pattern.findall(text)
    if len(found) == 2 and all(len(part.split()) >= 2 for part in found):
        return [part.strip() for part in found]
    return []


def split_authors(raw: Any) -> list[str]:
    """Разбивает строку авторов на отдельные имена.

    Поддерживаются форматы:
      * ``Gogovor A., Savoie M., Moride Y.`` — через запятую;
      * ``Финогенов А. А., Е. И. Фролов`` — инициалы перед фамилией;
      * ``Фамилия, И. О.; Другая, П. К.`` — через точку с запятой;
      * ``Иванов И. И. Петров П. П.`` — без разделителей;
      * ``Gogovor A.`` / ``A. Gogovor`` / ``A Gogovor``.

    Запятая ВНУТРИ имени («Фамилия, И. О.») не считается разделителем.
    """
    if isinstance(raw, (list, tuple)):
        items = [clean(x) for x in raw if clean(x)]
        return [x for x in items if x.lower().strip(" .") not in _NOT_AUTHOR]

    text = clean(raw)
    if not text:
        return []
    if text.lower().strip(" .") in _NOT_AUTHOR:
        return []

    text = re.sub(r"\s+", " ", text.replace("&", ";")).strip(" ;,")

    if ";" in text:
        parts = text.split(";")
    else:
        parts = _split_by_commas(text)

    result: list[str] = []
    for part in parts:
        cleaned = clean(part).strip(" ,;")
        if not cleaned:
            continue
        if cleaned.lower().strip(" .") in _NOT_AUTHOR:
            continue
        result.append(cleaned)
    return result


def _split_by_commas(text: str) -> list[str]:
    """Делит по запятым, не разрывая «Фамилия, И. О.» и «Gogovor A., Savoie M.»."""
    # 1. «Фамилия, И. О.» — запятая внутри одной записи автора.
    inside = re.compile(
        r"([А-ЯЁA-Z][а-яёa-z-]+),\s*((?:[А-ЯЁA-Z]\.\s*(?:[А-ЯЁA-Z]\.\s*)?)+)"
    )
    # 2. «IVANOV, Ivan Ivanovich» — запятая между фамилией и полным именем.
    full_name = re.compile(
        r"^([А-ЯЁA-Z][а-яёa-z-]+),\s*([А-ЯЁA-Z][а-яёa-z-]+(?:\s+[А-ЯЁA-Z][а-яёa-z-]+)+)$"
    )
    if full_name.match(text.strip()):
        return [text.strip()]

    if inside.search(text) and not re.search(r",\s*[А-ЯЁA-Z]\.", text):
        parts = [m.group(1) + " " + m.group(2).strip() for m in inside.finditer(text)]
        if parts:
            return parts

    parts = [p for p in re.split(r",\s*", text) if p.strip()]

    merged: list[str] = []
    for part in parts:
        part = part.strip()
        # Отдельно стоящие инициалы принадлежат предыдущей записи.
        if merged and re.fullmatch(r"(?:[А-ЯЁA-Z]\.\s*){1,3}", part):
            merged[-1] = f"{merged[-1]} {part}"
            continue
        # Предыдущая запись закончилась инициалами — новый автор не при чём.
        merged.append(part)

    # «Иванов И. И. Петров П. П.» — два автора без разделителя.
    expanded: list[str] = []
    for part in merged:
        if len(part.split()) >= 4 and re.search(r"[А-ЯЁA-Z]\.", part):
            pair = _split_two_authors(part)
            if pair:
                expanded.extend(pair)
                continue
        expanded.append(part)

    return expanded




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

    # Форма «Фамилия И О» (инициалы без точек, как в части источников).
    match = re.match(r"^([^.\s]+)\s+([А-ЯЁA-Z](?:\s+[А-ЯЁA-Z]){0,2})$", text)
    if match and len(match.group(2).replace(" ", "")) <= 3:
        return match.group(1).strip(), list(match.group(2).replace(" ", ""))

    # Форма «И.О. Фамилия»
    match = re.match(r"^((?:[А-ЯЁA-Z]\.\s*){1,3})\s*(.+)$", text)
    if match:
        initials = re.findall(r"[А-ЯЁA-Z]", match.group(1))
        return match.group(2).strip(), initials

    parts = text.split()
    if len(parts) >= 2 and all(_INITIALS_RE.match(p) for p in parts[1:]):
        initials = [p.replace(".", "")[:1] for p in parts[1:]]
        return parts[0], initials

    # «Фамилия, И. О.» — запятая уже убрана, но инициалы могли остаться.
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
    """Приоритет: DOI → URL. Нестандартный, но подтверждённый URL сохраняется."""
    doi = norm_doi(record.get("doi"))
    if is_doi_like(doi):
        return doi_url(doi)
    url = clean(record.get("url"))
    if url.startswith(("http://", "https://")):
        return url
    return ""


def _resolve_container(record: Mapping[str, Any]) -> str:
    """Реальный источник публикации: контейнер, журнал или выпуск."""
    for key in ("container", "journal", "source_title", "publication"):
        value = clean(record.get(key))
        if value and not is_forbidden_container(value):
            return value
    return ""


def build_citation(
    record: Mapping[str, Any],
    *,
    moment: date | datetime | None = None,
) -> str:
    """Собирает библиографическую ссылку по принятому в проекте формату.

    Неизвестные части опускаются. Если автора нет, ссылка начинается с
    названия — фиктивное «Автор не указан» не печатается.
    """
    title = clean(record.get("title_original") or record.get("title"))
    container = _resolve_container(record)

    authors = split_authors(record.get("authors") or record.get("author"))

    year_verdict = check_year(record.get("year"))
    year = str(year_verdict.year) if year_verdict.status == "ok" else ""

    url = _resolve_url(record)
    access = format_access_date(moment)

    parts: list[str] = []

    # Блок 1: авторы и название. Без автора — сразу название.
    head = ""
    if title:
        head = title
    if authors:
        first = format_first_author(authors[0])
        rest = [format_other_author(a) for a in authors[1:]]
        rest = [r for r in rest if r]
        if first:
            head = f"{first}. {title}" if title else f"{first}."
            if rest:
                head += " / " + ", ".join(rest)
    if head:
        parts.append(head)

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
    for chunk in parts[1:]:
        # Перед блоком журнала уже стоит «//», поэтому «. – » не дублируем.
        result += " " + chunk if chunk.startswith("//") else ". – " + chunk
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
