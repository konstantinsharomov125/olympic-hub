"""Удаление дублей: сначала по DOI/ISBN, затем по названию и авторам.

Похожие названия не объединяются автоматически: совпадение нормализованного
названия требуется вместе с совпадением первого автора и года, иначе
запись остаётся отдельной. Разные издания, годы и самостоятельные
публикации с похожим названием сохраняются.

Нормализация названий учитывает кириллические/латинские гомоглифы
(«Олимпийское» и «Olympic» сравниваются по одним и тем же символам),
разные варианты написания (дефисы, кавычки, регистр) и знаки препинания.
"""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any, Iterable, Mapping

from olympic_hub_core import clean, norm_doi, norm_isbn, norm_key

#: Минимальная длина нормализованного названия для сравнения.
MIN_TITLE_KEY_LEN = 20
#: Порог сходства для «содержательно похожих» названий.
SIMILARITY_THRESHOLD = 0.93


def _first_author_key(record: Mapping[str, Any]) -> str:
    raw = clean(record.get("authors") or record.get("author"))
    if not raw:
        return ""
    first = raw.split(";")[0]
    # «Фамилия И. О.» / «Фамилия, И. О.» — фамилия до запятой или инициалов.
    head = first.split(",")[0].strip() or first
    tokens = [t for t in head.replace(".", ". ").split() if t]
    surname = tokens[0] if tokens else head
    return norm_key(surname)


def _title_key(record: Mapping[str, Any]) -> str:
    title = clean(record.get("title_original") or record.get("title"))
    normalized = norm_key(title)
    return normalized if len(normalized) >= MIN_TITLE_KEY_LEN else ""


def _similar_titles(a: str, b: str) -> bool:
    """Содержательное сходство названий (только для отчёта, без слияния)."""
    if not a or not b:
        return False
    if abs(len(a) - len(b)) > max(10, int(0.15 * max(len(a), len(b)))):
        return False
    return SequenceMatcher(None, a, b).ratio() >= SIMILARITY_THRESHOLD


def _merge_into(primary: dict[str, Any], secondary: Mapping[str, Any]) -> None:
    """Дополняет основную запись недостающими полями дубля."""
    merged_from = primary.setdefault("merged_from", [])

    # Сохраняем сведения об источниках обеих записей.
    source_urls = primary.setdefault("source_urls", [])
    for url in (primary.get("url"), secondary.get("url")):
        if url and url not in source_urls:
            source_urls.append(url)
    for url in secondary.get("source_urls") or []:
        if url and url not in source_urls:
            source_urls.append(url)

    for key, value in secondary.items():
        if key in {"merged_from", "source_urls", "study_id", "relevance_status", "relevance_reason"}:
            continue
        current = primary.get(key)
        if (current is None or clean(current) == "") and value is not None and clean(value) != "":
            primary[key] = value

    identifier = secondary.get("study_id") or secondary.get("doi") or "без идентификатора"
    if identifier not in merged_from:
        merged_from.append(identifier)


def deduplicate(
    records: Iterable[Mapping[str, Any]],
) -> tuple[list[dict], list[dict]]:
    """Возвращает (уникальные записи, список объединённых дублей)."""
    unique: list[dict] = []
    duplicates: list[dict] = []

    by_doi: dict[str, int] = {}
    by_isbn: dict[str, int] = {}

    # Проход 1: объединение по DOI и ISBN.
    for record in records:
        item = dict(record)
        doi = norm_doi(item.get("doi"))
        isbn = norm_isbn(item.get("isbn"))

        if doi and doi in by_doi:
            target = unique[by_doi[doi]]
            _merge_into(target, item)
            duplicates.append(
                {
                    "kept": target.get("study_id"),
                    "merged": item.get("study_id"),
                    "reason": f"совпадение DOI {doi}",
                }
            )
            continue
        if isbn and isbn in by_isbn:
            target = unique[by_isbn[isbn]]
            _merge_into(target, item)
            duplicates.append(
                {
                    "kept": target.get("study_id"),
                    "merged": item.get("study_id"),
                    "reason": f"совпадение ISBN {isbn}",
                }
            )
            continue

        if doi:
            by_doi[doi] = len(unique)
        if isbn:
            by_isbn[isbn] = len(unique)
        unique.append(item)

    # Проход 2: название + первый автор + год.
    by_signature: dict[tuple[str, str, str], int] = {}
    result: list[dict] = []

    for item in unique:
        title_key = _title_key(item)
        author_key = _first_author_key(item)
        year_key = clean(item.get("year"))

        if title_key and author_key and year_key:
            signature = (title_key, author_key, year_key)
            if signature in by_signature:
                target = result[by_signature[signature]]
                _merge_into(target, item)
                duplicates.append(
                    {
                        "kept": target.get("study_id"),
                        "merged": item.get("study_id"),
                        "reason": "совпадение названия, первого автора и года",
                    }
                )
                continue
            by_signature[signature] = len(result)

        result.append(item)

    return result, duplicates


def find_similar_pairs(
    records: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Находит похожие, но НЕ объединённые записи — только для отчёта аудита.

    Здесь ничего не сливается: цель — показать человеку пары, которые
    стоит проверить (например, разные издания или переводы одной работы).
    Условие — тот же год и тот же первый автор плюс высокое сходство названий.
    """
    items = [rec for rec in records if _title_key(rec)]
    pairs: list[dict[str, Any]] = []
    for index, first in enumerate(items):
        for second in items[index + 1 :]:
            if clean(first.get("year")) != clean(second.get("year")):
                continue
            if _first_author_key(first) != _first_author_key(second):
                continue
            if _similar_titles(_title_key(first), _title_key(second)):
                pairs.append(
                    {
                        "a": first.get("study_id"),
                        "b": second.get("study_id"),
                        "title_a": clean(first.get("title_original"))[:120],
                        "title_b": clean(second.get("title_original"))[:120],
                        "year": clean(first.get("year")),
                    }
                )
    return pairs

