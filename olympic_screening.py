"""Структурная фильтрация: отделяет самостоятельные публикации от мусора.

Из публичного каталога исключаются записи, которые не являются научными
публикациями: служебные разделы книг (Frontmatter, Contents, Index,
Illustrations, Bibliography, Acknowledgements, List of Abbreviations),
одиночные структурные слова, заголовки глав без самостоятельного текста,
фрагменты оглавлений, рецензии и служебные записи библиотек.

Правило осторожности: полноценная статья не отбрасывается только из-за
номера главы в названии или непривычной структуры. Сомнительные записи
направляются в ``review``, а не в ``rejected``.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

from olympic_hub_core import clean

#: Коды решения структурной проверки.
STRUCTURE_OK = "ok"
STRUCTURE_REVIEW = "review"
STRUCTURE_REJECT = "reject"

#: Служебные разделы: название целиком состоит из структурного слова.
STRUCTURAL_TITLES: frozenset[str] = frozenset(
    {
        "frontmatter", "front matter", "title page", "half title", "colophon",
        "contents", "table of contents", "содержание", "оглавление",
        "index", "name index", "author index", "subject index", "указатель",
        "illustrations", "list of illustrations", "список иллюстраций",
        "figures", "list of figures", "tables", "list of tables",
        "bibliography", "references", "literature", "список литературы",
        "библиография", "acknowledgements", "acknowledgments", "благодарности",
        "abbreviations", "list of abbreviations", "сокращения", "условные сокращения",
        "abstract", "аннотация", "preface", "предисловие", "introduction",
        "введение", "conclusion", "заключение", "appendix", "приложение",
        "appendices", "glossary", "глоссарий", "notes", "примечания",
        "cover", "обложка", "copyright", "imprint", "dedication", "посвящение",
        "notes on contributors", "about the authors", "notes on the authors",
    }
)

#: Номер главы/раздела в начале названия («Глава 6 …», «Гл. 3», «Chapter 2»).
_CHAPTER_PREFIX_RE = re.compile(
    r"^\s*(?:глава|гл\.|раздел|часть|chapter|section|part|abschnitt|kapitel)\s*"
    r"(?:\d+|[IVXLC]+)\b[.:)]?\s*",
    re.I,
)
#: Только номер и структурное слово: «Глава 6», «3. Contents», «§ 2.1 Index».
_NUMBERED_STRUCTURAL_RE = re.compile(
    r"^\s*(?:глава|гл\.|раздел|часть|chapter|section|part)?\s*"
    r"(?:\d+(?:\.\d+)*|[IVXLC]+)?[.:)]?\s*"
    r"(?:frontmatter|contents|index|illustrations|bibliography|acknowledg\w*|"
    r"abbreviations|appendix|glossary|notes|references|содержание|оглавление|"
    r"указатель|иллюстрации|библиограф\w*|благодарности|сокращения|приложение)\s*$",
    re.I,
)

#: Признаки рецензии и служебной записи.
REVIEW_MARKERS_RE = re.compile(
    r"\b(?:book\s+review|рецензия|review\s+of\s+the\s+book|new\s+books?|"
    r"books?\s+received|list\s+of\s+new\s+publications|contents\s+pages)\b",
    re.I,
)

#: Одиночные структурные слова, которые не могут быть названием статьи.
SHORT_STRUCTURAL_RE = re.compile(
    r"^(?:frontmatter|contents|index|illustrations|bibliography|acknowledg\w*|"
    r"abbreviations|preface|introduction|conclusion|notes|references|cover|"
    r"содержание|оглавление|указатель|библиография|предисловие|введение|заключение)$",
    re.I,
)

#: Типы документов, которые в принципе не могут попасть в каталог.
NON_PUBLICATION_TYPES_RE = re.compile(
    r"^(?:book\s+chapter\s+abstract|frontmatter|backmatter|table\s+of\s+contents|"
    r"содержание|оглавление)$",
    re.I,
)


def is_structural_title(title: Any) -> bool:
    """True, если название — служебный раздел книги."""
    value = clean(title).strip(" .,;:—-–")
    if not value:
        return True
    lowered = value.lower()
    if lowered in STRUCTURAL_TITLES:
        return True
    if _NUMBERED_STRUCTURAL_RE.match(value):
        return True
    if SHORT_STRUCTURAL_RE.match(value) and len(value) < 25:
        return True
    return False


def has_chapter_number(title: Any) -> bool:
    """Название начинается с номера главы, но содержит содержательный текст."""
    return bool(_CHAPTER_PREFIX_RE.match(clean(title)))


def screen_structure(record: Mapping[str, Any]) -> dict[str, str]:
    """Классифицирует запись по структуре.

    Возвращает ``{"code": ok|review|reject, "reason": str}``.
    Заголовок главы с содержательным названием НЕ отбрасывается: он
    проходит дальше, потому что может быть самостоятельной главой-статьёй.
    """
    title = clean(record.get("title_original") or record.get("title"))
    abstract = clean(record.get("abstract_original"))
    doc_type = clean(record.get("document_type") or record.get("type"))
    container = clean(record.get("container") or record.get("source"))

    if not title:
        return {"code": STRUCTURE_REVIEW, "reason": "Название отсутствует"}

    if NON_PUBLICATION_TYPES_RE.match(doc_type):
        return {
            "code": STRUCTURE_REJECT,
            "reason": f"Тип записи «{doc_type}» не является научной публикацией",
        }

    if is_structural_title(title):
        return {
            "code": STRUCTURE_REJECT,
            "reason": "Служебный раздел книги (оглавление, указатель, список литературы и т. п.)",
        }

    if REVIEW_MARKERS_RE.search(title):
        return {
            "code": STRUCTURE_REVIEW,
            "reason": "Похоже на рецензию или служебную библиографическую заметку",
        }

    # Заголовок главы без аннотации и названия выпуска — сомнительная запись.
    if has_chapter_number(title) and not abstract and not container:
        return {
            "code": STRUCTURE_REVIEW,
            "reason": "Заголовок главы без аннотации и данных о выпуске",
        }

    return {"code": STRUCTURE_OK, "reason": ""}
