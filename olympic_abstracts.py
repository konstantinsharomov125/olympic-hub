"""Работа с аннотациями: очистка псевдотекстов и честные статусы.

Каталог не должен выдавать сгенерированный текст за авторскую аннотацию.
Модуль распознаёт шаблонные заглушки, удаляет их и проставляет статус,
по которому интерфейс показывает понятное сообщение.

Дополнительно (после аудита): удаляются HTML-сущности и мусорные
последовательности вроде ``&s;s`` и ``&#x0D;``, УДК/ББК и издательские
сведения, попавшие в начало аннотации, а также дублирующиеся служебные
фрагменты. Название статьи никогда не подменяет аннотацию.
"""

from __future__ import annotations

import html
import re
from typing import Any, Mapping

from olympic_hub_core import clean

#: Статусы аннотации, которые понимает интерфейс.
ABS_PRESENT = "present"        # есть настоящая аннотация из источника
ABS_NONE = "missing"           # аннотации в источнике нет
ABS_SYNTHETIC = "synthetic"    # была заглушка, удалена
ABS_AI = "ai_summary"          # автоматическое резюме, не авторский текст
ABS_TRUNCATED = "truncated"    # аннотация оборвана в источнике

#: Сообщение для интерфейса, когда аннотации нет.
MISSING_MESSAGE = "Аннотация не найдена в источнике"
#: Сообщение, когда аннотация есть, но она оборвана.
TRUNCATED_MESSAGE = "Аннотация в источнике оборвана"

#: Шаблоны, по которым распознаются выдуманные аннотации.
FAKE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^\s*научное\s+исследование\s+по\s+теме", re.I),
    re.compile(r"^\s*(?:данн|эта|это)\w*\s+(?:статья|работа|исследование)\s+посвящен", re.I),
    re.compile(r"^\s*(?:this|the)\s+(?:study|paper|article)\s+(?:is\s+)?(?:devoted|dedicated)\s+to\s+(?:the\s+)?(?:study|topic)\s+of\s+olymp", re.I),
    re.compile(r"^\s*в\s+данной\s+работе\s+рассматривается\s+тема\s+олимп", re.I),
    re.compile(r"^\s*аннотация\s+(?:к\s+)?(?:работе|статье)\s+по\s+теме", re.I),
    re.compile(r"^\s*статья\s+посвящена\s+олимпийской\s+тематике", re.I),
    re.compile(r"^\s*(?:the\s+)?(?:article|paper)\s+is\s+devoted\s+to\s+the\s+olympic\s+topic", re.I),
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
        "аннотация доступна по ссылке",
        "n/a",
        "na",
        "none",
        "null",
        "-",
        "—",
    }
)

#: Заглушки «аннотация по ссылке» и аналогичные конструкции.
_LINK_STUB_RE = re.compile(
    r"^(?:полн\w*\s+)?(?:текст|аннотаци\w*|abstract|full\s+text)\s+"
    r"(?:доступ\w*|представлен\w*|опубликован\w*)?\s*"
    r"(?:по\s+ссылке|на\s+сайте|в\s+источнике|в\s+оригинале|в\s+первоисточнике|online|here)\W*$"
    r"|^аннотаци\w*\s+(?:доступна|представлена)\s+по\s+ссылке\W*$"
    r"|^(?:see|view)\s+(?:the\s+)?(?:full\s+text|abstract)\s+(?:online|at\s+the\s+link)\W*$",
    re.I,
)

#: Начало аннотации, забитое библиографическими/издательскими данными.
_BIBLIO_PREFIX_RE = re.compile(
    r"^\s*(?:УДК|ББК|UDC|DOI|ISBN|ISSN)\s*[:№]?\s*[\d\w.\-/]+\s*[.;:]?\s*",
    re.I,
)

#: Издательские фразы в начале текста.
_PUBLISHER_PREFIX_RE = re.compile(
    r"^\s*(?:Издательство|Изд-во|Publisher|©|\(c\)|Copyright)\s*[^.]{0,80}\.\s*",
    re.I,
)

#: Мусорные последовательности, попадающие из HTML/XML.
_JUNK_SEQUENCE_RE = re.compile(
    r"&[a-zA-Z]{1,8};|&#x?[0-9a-fA-F]{1,6};|&#x0D;|&#13;|&#10;",
    re.I,
)
#: Служебные фрагменты, повторяющиеся в тексте.
_SERVICE_FRAGMENT_RE = re.compile(
    r"(?:\b(?:Аннотация|Abstract)\s*[:.]\s*){2,}|\b(?:Keywords|Ключевые\s+слова)\s*:\s*(?=\bKeywords\s*:)",
    re.I,
)


def _strip_html(text: str) -> str:
    """Убирает теги и раскрывает HTML-сущности."""
    without_tags = re.sub(r"<[^>]{1,200}>", " ", text)
    # Двойное раскрытие: в данных встречается «&amp;s;s».
    decoded = html.unescape(without_tags)
    decoded = html.unescape(decoded)
    return decoded


def _remove_junk(text: str) -> str:
    """Удаляет мусорные сущности и лишние пробелы."""
    result = _JUNK_SEQUENCE_RE.sub(" ", text)
    result = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", result)
    result = re.sub(r"[ \t\u00a0]+", " ", result)
    return result.strip()


def _strip_bibliographic_preamble(text: str) -> str:
    """Снимает УДК/ББК/ISBN и издательские сведения из начала текста."""
    result = text
    for _ in range(4):
        before = result
        result = _BIBLIO_PREFIX_RE.sub("", result)
        result = _PUBLISHER_PREFIX_RE.sub("", result)
        if result == before:
            break
    return result.strip()


def _dedupe_fragments(text: str) -> str:
    """Убирает дублирующиеся служебные фрагменты и повторы предложений."""
    result = _SERVICE_FRAGMENT_RE.sub(" ", text)
    sentences = re.split(r"(?<=[.!?])\s+", result)
    seen: set[str] = set()
    kept: list[str] = []
    for sentence in sentences:
        key = re.sub(r"\W+", " ", sentence.lower()).strip()
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        kept.append(sentence)
    return " ".join(kept).strip()


def _looks_truncated(text: str) -> bool:
    """Обрыв аннотации: нет завершающего знака и текст обрывается на полуслове."""
    value = text.rstrip()
    if len(value) < 120:
        return False
    if value.endswith((".", "!", "?", "…", ")", '"', "»")):
        return False
    last = value.split()[-1] if value.split() else ""
    # Обрывом считаем только явные признаки: одиночная буква или открытая скобка/кавычка.
    return bool(re.search(r"[(\[«\"]$", value)) or (len(last) <= 1)



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
    value = clean(text)
    if not value:
        return True
    lowered = value.lower()
    return lowered in PLACEHOLDERS or bool(_LINK_STUB_RE.match(value))


def clean_abstract_text(text: Any) -> tuple[str, bool]:
    """Очищает текст аннотации от мусора.

    Возвращает ``(очищенный_текст, был_мусор)``. Пустая строка означает,
    что настоящей аннотации не осталось.
    """
    value = clean(text)
    if not value:
        return "", False

    original = value
    value = _strip_html(value)
    value = _remove_junk(value)
    value = _strip_bibliographic_preamble(value)
    value = _dedupe_fragments(value)
    value = re.sub(r"\s{2,}", " ", value).strip()

    # Если после очистки остался только набор символов — текста нет.
    if len(re.sub(r"[^\w]", "", value)) < 8:
        value = ""
    return value, value != original


def looks_like_title(text: Any, title: Any) -> bool:
    """Аннотация не может быть повторением названия статьи."""
    value = clean(text).lower()
    heading = clean(title).lower()
    if not value or not heading:
        return False
    strip = lambda s: re.sub(r"\W+", " ", s).strip()  # noqa: E731
    return strip(value) == strip(heading) or (
        len(strip(value)) > 10 and strip(value) in strip(heading)
    )



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

    title = clean(out.get("title_original") or out.get("title"))
    original = clean(
        out.get("abstract_original")
        or out.get("summary_original")
        or out.get("summary")
        or out.get("abstract")
    )
    translated = clean(out.get("abstract_ru") or out.get("summary_ru"))
    removed_fake = False
    cleaned_artifacts = False

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

    # HTML-сущности, УДК/ББК, издательские сведения и дубли фрагментов.
    if original:
        original, changed = clean_abstract_text(original)
        cleaned_artifacts = cleaned_artifacts or changed
    if translated:
        translated, changed = clean_abstract_text(translated)
        cleaned_artifacts = cleaned_artifacts or changed

    # Название статьи не является аннотацией.
    if original and looks_like_title(original, title):
        original = ""
        removed_fake = True
    if translated and looks_like_title(translated, title):
        translated = ""
        removed_fake = True

    # Перевод, идентичный оригиналу, переводом не является.
    if translated and original and translated == original:
        translated = ""

    truncated = bool(original or translated) and _looks_truncated(translated or original)

    out["abstract_original"] = original
    out["abstract_ru"] = translated
    out["abstract_removed_fake"] = removed_fake
    out["abstract_cleaned"] = cleaned_artifacts
    out["abstract_truncated"] = truncated

    # Исходные поля-дубли тоже очищаются: иначе фильтр релевантности
    # снова прочитает заглушку как «настоящую» аннотацию.
    out["summary"] = original
    out["summary_original"] = original
    out["summary_ru"] = translated
    out["abstract"] = original

    if original:
        out["abstract_status"] = ABS_PRESENT
    else:
        out["abstract_status"] = ABS_SYNTHETIC if removed_fake else ABS_NONE
    display = translated or original
    if not display:
        display = MISSING_MESSAGE
    elif truncated:
        display = display.rstrip() + " […] " + TRUNCATED_MESSAGE.lower()
    out["abstract_display"] = display
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
