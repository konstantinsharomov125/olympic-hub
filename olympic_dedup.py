"""Удаление дублей: сначала по DOI, затем по названию и авторам.

Похожие названия не объединяются автоматически: совпадение нормализованного
названия требуется вместе с совпадением первого автора и года, иначе
запись остаётся отдельной.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from olympic_hub_core import clean, norm_doi, norm_text

#: Минимальная длина нормализованного названия для сравнения.
MIN_TITLE_KEY_LEN = 20


def _first_author_key(record: Mapping[str, Any]) -> str:
    raw = clean(record.get("authors") or record.get("author"))
    if not raw:
        return ""
    first = raw.split(";")[0].split(",")[0].strip()
    normalized = norm_text(first)
    return normalized


def _title_key(record: Mapping[str, Any]) -> str:
    title = clean(record.get("title_original") or record.get("title"))
    normalized = norm_text(title)
    return normalized if len(normalized) >= MIN_TITLE_KEY_LEN else ""


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

    # Проход 1: объединение по DOI.
    for record in records:
        item = dict(record)
        doi = norm_doi(item.get("doi"))

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

        if doi:
            by_doi[doi] = len(unique)
        unique.append(item)

    # Проход 2: название + первый автор + год.
    by_signature: dict[tuple[str, str, str], int] = {}
    result: list[dict] = []

    for item in unique:
        title_key = _title_key(item)
        author_key = _first_author_key(item)
        year_key = clean(item.get("year"))

        if title_key and author_key:
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
