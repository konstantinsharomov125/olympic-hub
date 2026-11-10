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


_DOI_PREFIX = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", re.I)


def norm_doi(value: Any) -> str:
    doi = clean(value)
    doi = _DOI_PREFIX.sub("", doi)
    return doi.rstrip(" .,;/").lower()


def doi_url(doi: Any) -> str:
    normalized = norm_doi(doi)
    return f"https://doi.org/{normalized}" if normalized else ""


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


