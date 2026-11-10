"""Общие утилиты Olympic Research Hub.

Единый источник правды для:
  * контракта данных ``{"metadata": {...}, "data": [...]}``;
  * нормализации DOI, текста и проверки годов;
  * тематической таксономии каталога.

Модуль не зависит от сторонних библиотек.
"""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

DATA_ENVELOPE_VERSION = 2
METADATA_KEY = "metadata"
DATA_KEY = "data"


class DataContractError(ValueError):
    """Файл данных не соответствует формату {metadata, data}."""


def make_envelope(
    records: Iterable[Mapping[str, Any]],
    *,
    source: str,
    generated_at: str | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Собирает корректный конверт данных."""
    records = list(records)
    metadata: dict[str, Any] = {
        "schema_version": DATA_ENVELOPE_VERSION,
        "generated_at_utc": generated_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": source,
        "record_count": len(records),
    }
    if extra:
        metadata.update(extra)
    return {METADATA_KEY: metadata, DATA_KEY: records}


def read_envelope(payload: Any, *, strict: bool = True) -> tuple[dict[str, Any], list[Any]]:
    """Возвращает (metadata, records) из конверта."""
    if isinstance(payload, list):
        if strict:
            raise DataContractError(
                "Ожидался объект {metadata, data}, получен массив. "
                "Данные нужно привести к единому контракту."
            )
        return {}, payload

    if not isinstance(payload, dict):
        raise DataContractError(f"Неожиданный корневой тип данных: {type(payload).__name__}")

    if DATA_KEY in payload:
        records = payload[DATA_KEY]
        if not isinstance(records, list):
            raise DataContractError("Поле 'data' должно быть массивом")
        metadata = payload.get(METADATA_KEY) or {}
        if not isinstance(metadata, dict):
            raise DataContractError("Поле 'metadata' должно быть объектом")
        return metadata, records

    for legacy_key in ("items", "records"):
        if legacy_key in payload and isinstance(payload[legacy_key], list):
            if strict:
                raise DataContractError(f"Найден легаси-ключ '{legacy_key}'. Ожидается 'data'.")
            return payload.get(METADATA_KEY) or {}, payload[legacy_key]

    raise DataContractError("В файле нет поля 'data'")


def load_envelope(path: str | Path, *, strict: bool = True) -> tuple[dict[str, Any], list[Any]]:
    with open(path, "r", encoding="utf-8") as fh:
        return read_envelope(json.load(fh), strict=strict)


def dump_envelope(envelope: Mapping[str, Any], path: str | Path, *, indent: int | None = None) -> None:
    """Атомарная запись конверта: временный файл, затем замена."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        if indent is None:
            json.dump(envelope, fh, ensure_ascii=False, separators=(",", ":"))
        else:
            json.dump(envelope, fh, ensure_ascii=False, indent=indent)
    tmp.replace(path)


def validate_envelope(envelope: Any) -> list[str]:
    """Возвращает список проблем. Пустой список — данные валидны."""
    problems: list[str] = []
    try:
        metadata, records = read_envelope(envelope, strict=True)
    except DataContractError as exc:
        return [str(exc)]

    if "record_count" not in metadata:
        problems.append("metadata.record_count отсутствует")
    elif metadata["record_count"] != len(records):
        problems.append(
            f"metadata.record_count={metadata['record_count']} != len(data)={len(records)}"
        )
    if not metadata.get("source"):
        problems.append("metadata.source отсутствует")
    if not metadata.get("generated_at_utc"):
        problems.append("metadata.generated_at_utc отсутствует")

    for idx, record in enumerate(records):
        if not isinstance(record, dict):
            problems.append(f"data[{idx}] не является объектом")
            continue
        if not record.get("study_id"):
            problems.append(f"data[{idx}] без study_id")
    return problems


# --------------------------------------------------------------------------
# Нормализация
# --------------------------------------------------------------------------


def clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\ufeff", "").strip()


def norm_text(value: Any) -> str:
    """Нормализация для сравнения: нижний регистр, без пунктуации."""
    text = unicodedata.normalize("NFKC", clean(value)).lower().replace("ё", "е")
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


#: Кириллические и латинские буквы, которые выглядят одинаково.
#: При сравнении названий (дедупликация) они приводятся к латинице,
#: чтобы «Oлимпийское» и «Olympic» совпадали по символам.
_CYRILLIC_HOMOGLYPHS = str.maketrans(
    {
        "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x",
        "к": "k", "м": "m", "т": "t", "в": "b", "н": "h", "і": "i", "ј": "j",
        "ѕ": "s", "ԁ": "d", "ԛ": "q", "ԝ": "w",
    }
)


def norm_key(value: Any) -> str:
    """Ключ сравнения: ``norm_text`` + нормализация гомоглифов.

    Используется только для дедупликации, исходные поля не меняются.
    """
    text = norm_text(value)
    return text.translate(_CYRILLIC_HOMOGLYPHS)



_DOI_PREFIX = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", re.I)


def norm_doi(value: Any) -> str:
    doi = clean(value)
    doi = _DOI_PREFIX.sub("", doi)
    return doi.rstrip(" .,;/").lower()


def doi_url(doi: Any) -> str:
    normalized = norm_doi(doi)
    return f"https://doi.org/{normalized}" if normalized else ""


# --------------------------------------------------------------------------
# ISBN (книжные издания)
# --------------------------------------------------------------------------

_ISBN_PREFIX = re.compile(r"^\s*(?:isbn(?:-1[03])?\s*:?\s*)", re.I)


def norm_isbn(value: Any) -> str:
    """Приводит ISBN к цифровой форме (10 или 13 знаков) с сохранением X."""
    text = _ISBN_PREFIX.sub("", clean(value))
    digits = re.sub(r"[^0-9xX]", "", text).upper()
    if len(digits) in (10, 13):
        return digits
    return ""


def isbn_from_identifiers(*values: Any) -> str:
    """Ищет ISBN среди идентификаторов (URL, DOI-подобных строк, примечаний).

    Проверка строгая: цифры ISBN-10/13 сливаются и валидируются контрольной
    суммой, чтобы номер года или страница не были приняты за ISBN.
    """
    for value in values:
        text = clean(value)
        if not text:
            continue
        for run in re.findall(r"\d[\dXx-]{8,20}\d", text):
            candidate = norm_isbn(run)
            if not candidate:
                continue
            if len(candidate) == 13 and _isbn13_valid(candidate):
                return candidate
            if len(candidate) == 10 and _isbn10_valid(candidate):
                return candidate
    return ""


def _isbn10_valid(value: str) -> bool:
    total = sum((10 - index) * (10 if char == "X" else int(char)) for index, char in enumerate(value))
    return total % 11 == 0


def _isbn13_valid(value: str) -> bool:
    total = sum((1 if index % 2 == 0 else 3) * int(char) for index, char in enumerate(value))
    return total % 10 == 0



def is_doi_like(value: Any) -> bool:
    """DOI начинается с префикса ``10.``."""
    return bool(re.match(r"^10\.\d{4,9}/\S+$", norm_doi(value)))



# --------------------------------------------------------------------------
# Годы публикации
# --------------------------------------------------------------------------

OLYMPIC_FIRST_YEAR = 1896


class YearVerdict:
    """Результат проверки года: status = ok | review | invalid."""

    __slots__ = ("year", "status", "reason")

    def __init__(self, year: int | None, status: str, reason: str) -> None:
        self.year = year
        self.status = status
        self.reason = reason

    def __repr__(self) -> str:  # pragma: no cover
        return f"YearVerdict(year={self.year!r}, status={self.status!r}, reason={self.reason!r})"


class ScreenedYear:
    """Год после сверки поля и идентификатора.

    ``status``: ``ok`` — год подтверждён; ``review`` — года нет;
    ``conflict`` — поле и DOI/URL расходятся, нужен человек.
    """

    __slots__ = ("year", "source", "status", "reason")

    def __init__(self, year: int | None, source: str, reason: str) -> None:
        self.year = year
        self.source = source
        self.reason = reason
        # Порядок важен: расхождение и невозможный год важнее наличия числа.
        if source == "conflict":
            self.status = "conflict"
        elif source == "invalid":
            self.status = "invalid"
        elif year is None:
            self.status = "review"
        else:
            self.status = "ok"

    def __repr__(self) -> str:  # pragma: no cover
        return f"ScreenedYear(year={self.year!r}, source={self.source!r}, status={self.status!r})"


def parse_year(value: Any) -> int | None:
    text = clean(value)
    if not text:
        return None
    if re.fullmatch(r"\d{4}", text):
        return int(text)
    match = re.search(r"\b(1[89]\d{2}|20\d{2})\b", text)
    return int(match.group(1)) if match else None


def check_year(value: Any, *, current_year: int | None = None) -> YearVerdict:
    """Проверяет год, не подгоняя его под правдоподобный."""
    current = current_year or datetime.now(timezone.utc).year
    raw = clean(value)
    if not raw:
        return YearVerdict(None, "review", "Год публикации не указан")

    year = parse_year(raw)
    if year is None:
        return YearVerdict(None, "review", f"Год не распознан: {raw[:20]!r}")
    if year < OLYMPIC_FIRST_YEAR:
        return YearVerdict(year, "invalid", f"Год {year} раньше первых Игр 1896")
    if year > current:
        return YearVerdict(year, "invalid", f"Год {year} в будущем (текущий {current})")
    return YearVerdict(year, "ok", "")


# --------------------------------------------------------------------------
# Год, подтверждённый источником
# --------------------------------------------------------------------------

#: Годы, которые не могут быть датой публикации внутри публикации:
#: это либо ссылки в списке литературы, либо диапазоны «Игры 2016».
_YEAR_TOKEN = re.compile(r"(?<![\d.])(1[89]\d{2}|20\d{2})(?![\d])")


def years_in_text(text: Any) -> list[int]:
    return [int(m.group(1)) for m in _YEAR_TOKEN.finditer(clean(text))]


def resolve_year(record: Mapping[str, Any], *, current_year: int | None = None) -> ScreenedYear:
    """Определяет год публикации и объясняет, откуда он взят.

    Правила:
      * поле ``year`` — основной источник, если значение допустимо;
      * если его нет, недопустимо оно или противоречит году в DOI/URL,
        год берётся из идентификатора (там он реально напечатан);
      * ничего не угадывается: при отсутствии подтверждений возвращается
        статус ``review``, и запись в публичный каталог не попадает.

    ``year_source``: ``field`` — из поля, ``doi`` — из DOI/URL,
    ``missing`` — нет года, ``conflict`` — поле и идентификатор расходятся.
    """
    current = current_year or datetime.now(timezone.utc).year
    field_value = clean(record.get("year") or record.get("publication_year"))
    field_verdict = check_year(field_value, current_year=current)

    identifier = clean(record.get("doi")) or clean(record.get("url"))
    identifier_years = [
        year for year in years_in_text(identifier) if OLYMPIC_FIRST_YEAR <= year <= current
    ]
    id_year = identifier_years[0] if len(set(identifier_years)) == 1 else None

    if field_verdict.status == "ok":
        if id_year is not None and id_year != field_verdict.year:
            return ScreenedYear(
                field_verdict.year,
                "conflict",
                f"Год в поле {field_verdict.year} расходится с годом в DOI/URL ({id_year})",
            )
        return ScreenedYear(field_verdict.year, "field", "")

    if id_year is not None:
        return ScreenedYear(
            id_year,
            "doi",
            f"Год взят из DOI/URL: {id_year}. Поле «year» = {field_value or 'пусто'}",
        )

    if field_verdict.status == "invalid":
        return ScreenedYear(field_verdict.year, "invalid", field_verdict.reason)
    return ScreenedYear(None, "missing", field_verdict.reason)



# --------------------------------------------------------------------------
# Таксономия
# --------------------------------------------------------------------------

CATEGORY_EDUCATION = "Олимпийское образование и просвещение"
CATEGORY_PHILOSOPHY = "Пропаганда, философия и культурология"
CATEGORY_HISTORY = "История и наследие олимпизма"
CATEGORY_ETHICS = "Этика, честная игра и антидопинг"
CATEGORY_POLITICS = "Политика, геополитика и глобальные вызовы"
CATEGORY_PSYCHOLOGY = "Психология олимпийского спорта"
CATEGORY_MANAGEMENT = "Менеджмент, маркетинг и экономика Игр"
CATEGORY_MEDICINE = "Спортивная медицина, физиология и биомеханика"
CATEGORY_TRAINING = "Подготовка олимпийского резерва и тренировка"
CATEGORY_THEORY = "Теория и методология олимпийского движения"
CATEGORY_NONE = "Без категории"

#: Единый список направлений. Используется и в Python, и в интерфейсе.
CATEGORIES: tuple[str, ...] = (
    CATEGORY_EDUCATION,
    CATEGORY_PHILOSOPHY,
    CATEGORY_HISTORY,
    CATEGORY_ETHICS,
    CATEGORY_POLITICS,
    CATEGORY_PSYCHOLOGY,
    CATEGORY_MANAGEMENT,
    CATEGORY_MEDICINE,
    CATEGORY_TRAINING,
    CATEGORY_THEORY,
    CATEGORY_NONE,
)

#: Ключевые слова для обоснованного выбора направления.
CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    CATEGORY_EDUCATION: (
        "образован", "педагог", "воспитан", "учеб", "школ", "студент", "академи", "просвещен",
        "educat", "pedagog", "school", "curriculum", "university", "student", "teaching",
    ),
    CATEGORY_PHILOSOPHY: (
        "философ", "культур", "идеал", "ценност", "символ", "гуманизм", "пропаганд", "олимпизм",
        "philosoph", "culture", "value", "ideals", "symbol", "humanism", "propaganda", "olympism",
    ),
    CATEGORY_HISTORY: (
        "истор", "наслед", "традиц", "кубертен", "древн", "музей", "архив", "эволюц",
        "histor", "legacy", "heritage", "coubertin", "ancient", "archiv", "museum", "tradition",
    ),
    CATEGORY_ETHICS: (
        "этик", "допинг", "fair play", "честн", "коррупц", "вада", "wada", "integrity",
        "ethic", "doping", "anti-doping", "corruption",
    ),
    CATEGORY_POLITICS: (
        "политик", "бойкот", "санкц", "геополитик", "дипломат", "протест", "нейтральн",
        "politic", "boycott", "sanction", "geopolitic", "diplomacy", "protest", "soft power",
    ),
    CATEGORY_PSYCHOLOGY: (
        "психолог", "стресс", "мотивац", "тревож", "ментальн", "психофизио",
        "psycholog", "stress", "motivat", "anxiety", "mental", "coping",
    ),
    CATEGORY_MANAGEMENT: (
        "менедж", "эконом", "маркетинг", "спонсор", "инфраструктур", "бюджет", "туризм",
        "manag", "econom", "market", "sponsor", "infrastruct", "budget", "tourism",
    ),
    CATEGORY_MEDICINE: (
        "медицин", "физиолог", "биомехан", "травм", "реабилит", "восстановл", "диагност",
        "medicin", "physiol", "biomechan", "injury", "rehab", "recovery", "diagnost",
    ),
    CATEGORY_TRAINING: (
        "подготовк", "трениров", "резерв", "отбор", "нагруз", "вынослив", "результативн",
        "coach", "training", "reserve", "selection", "endurance", "performance",
    ),
    CATEGORY_THEORY: (
        "теория", "методол", "концепц", "структур", "систем", "модель", "движени",
        "theory", "methodolog", "concept", "structure", "system", "model",
    ),
}


