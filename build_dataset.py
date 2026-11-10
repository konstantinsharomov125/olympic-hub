"""Единая точка сборки датасета Olympic Research Hub.

Порядок:
  1. чтение источника (CSV Google Sheets или существующий JSON);
  2. нормализация записей;
  3. удаление дублей;
  4. проверка релевантности (accepted / rejected / review);
  5. очистка аннотаций от псевдотекстов;
  6. проверка годов;

Результат:
  public/web_data.json   — только принятые записи (публичный каталог)
  public/review.json     — записи на ручную проверку
  public/rejected.json   — отклонённые записи с причинами
  public/relevance_report.json — сводка решений

Сборка атомарна: при ошибке рабочие файлы не перезаписываются.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parent

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from olympic_abstracts import (  # noqa: E402
    ABS_NONE,
    ABS_PRESENT,
    ABS_SYNTHETIC,
    ABS_TRUNCATED,
    MISSING_MESSAGE,
    is_fake_abstract,
    sanitize_abstract_fields,
)
from olympic_dedup import deduplicate, find_similar_pairs  # noqa: E402
from olympic_hub_core import (  # noqa: E402
    CATEGORY_KEYWORDS,
    CATEGORY_NONE,
    check_year,
    clean,
    dump_envelope,
    is_doi_like,
    isbn_from_identifiers,
    make_envelope,
    norm_doi,
    norm_isbn,
    norm_text,
    resolve_year,
)
from olympic_relevance import (  # noqa: E402
    ACCEPTED,
    REJECTED,
    REVIEW,
    SUBJECT_OLYMPIAD,
    split_by_relevance,
)
from olympic_screening import screen_structure  # noqa: E402

PUBLIC_DIR = ROOT / "public"

#: Источник истины — мастер-датасет (CSV), а не старый корневой web_data.json.
DEFAULT_INPUT = ROOT / "generated" / "master_dataset.csv"



# --------------------------------------------------------------------------
# Нормализация записи
# --------------------------------------------------------------------------

def assign_category(record: Mapping[str, Any]) -> str:
    """Подбирает категорию по ключевым словам, иначе «Без категории».

    Никакого «наиболее вероятного» направления по умолчанию: если ни одно
    слово не совпало, запись остаётся без категории.
    """
    existing = clean(record.get("category"))
    text = norm_text(
        " ".join(
            [
                clean(record.get("title_original") or record.get("title")),
                clean(record.get("abstract_original") or record.get("summary")),
                clean(record.get("keywords")),
            ]
        )
    )
    if not text:
        return existing or CATEGORY_NONE

    scores: dict[str, int] = {}
    for category, words in CATEGORY_KEYWORDS.items():
        score = sum(text.count(norm_text(word)) for word in words if norm_text(word))
        if score:
            scores[category] = score

    if not scores:
        return CATEGORY_NONE

    best = max(scores, key=lambda key: scores[key])
    return best


def normalize_record(record: Mapping[str, Any], index: int) -> dict[str, Any]:
    """Нормализует запись ДО тематической проверки.

    Важно: аннотация очищается здесь же, потому что фильтр релевантности
    не имеет права опираться на сгенерированную заглушку.
    """
    out = dict(record)

    title = clean(out.get("title_original") or out.get("title"))
    authors = clean(out.get("authors") or out.get("author"))

    out["title_original"] = title
    out["authors"] = authors
    out["keywords"] = clean(out.get("keywords"))
    out["container"] = clean(out.get("container") or "")

    # Идентификаторы вычищаются до проверки года: год может браться из DOI.
    doi = norm_doi(out.get("doi"))
    if not is_doi_like(doi):
        doi = ""
    url = clean(out.get("url"))
    if not doi and is_doi_like(url):
        doi = norm_doi(url)
    out["doi"] = doi
    out["url"] = url if url.startswith(("http://", "https://")) else ""

    isbn = norm_isbn(out.get("isbn")) or isbn_from_identifiers(out.get("url"), out.get("doi"))
    out["isbn"] = isbn

    verdict = resolve_year(out)
    pending = out.get("year_pending")
    if verdict.status == "ok" and verdict.source == "field":
        out["year"] = str(verdict.year)
        out["year_status"] = "ok"
        out["year_source"] = "field"
        out["year_reason"] = ""
    elif verdict.status == "ok" and verdict.source == "doi" and pending:
        # Год взят из XML/регистрационной записи того же DOI — это подтверждение.
        out["year"] = str(verdict.year)
        out["year_status"] = "ok"
        out["year_source"] = "registry"
        out["year_reason"] = "Год подтверждён регистрационной записью DOI"
    elif verdict.status == "ok":
        out["year"] = str(verdict.year)
        out["year_status"] = "ok"
        out["year_source"] = "doi"
        out["year_reason"] = verdict.reason
    else:
        out["year"] = ""
        out["year_status"] = "review" if verdict.year is None else "invalid"
        out["year_source"] = verdict.source or "missing"
        out["year_reason"] = verdict.reason or "Год публикации не подтверждён"
        if verdict.year is not None:
            out["year_unverified_value"] = str(verdict.year)
    # Аннотация очищается до классификации: заглушки не считаются текстом.
    out = sanitize_abstract_fields(out)
    out["category"] = assign_category(out)
    out["doc_screen"] = screen_structure(out)

    if not out.get("study_id"):
        out["study_id"] = f"rec-{index:05d}"

    return out



def normalize_all(records: Iterable[Mapping[str, Any]]) -> list[dict]:
    return [normalize_record(rec, idx) for idx, rec in enumerate(records, start=1)]


# --------------------------------------------------------------------------
# Отчёты
# --------------------------------------------------------------------------

def build_relevance_report(
    accepted: list[dict],
    rejected: list[dict],
    review: list[dict],
    subject: list[dict],
    duplicates: list[dict],
    total_input: int,
    *,
    fake_removed: int = 0,
    cleaned_abstracts: int = 0,
    similar_pairs: list[dict] | None = None,
) -> dict[str, Any]:
    """Сводка решений по всему источнику."""

    def sample(items: list[dict], limit: int = 12) -> list[dict]:
        return [
            {
                "study_id": item.get("study_id"),
                "title": clean(item.get("title_original"))[:120],
                "reason": item.get("relevance_reason", ""),
            }
            for item in items[:limit]
        ]

    def count_where(items: list[dict], key: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in items:
            value = clean(item.get(key)) or "не указано"
            counts[value] = counts.get(value, 0) + 1
        return dict(sorted(counts.items(), key=lambda kv: -kv[1]))

    return {
        "input_records": total_input,
        "accepted": len(accepted),
        "rejected": len(rejected),
        "review": len(review),
        "subject_olympiad": len(subject),
        "duplicates_merged": len(duplicates),
        "fake_abstracts_removed": fake_removed,
        "abstracts_cleaned": cleaned_abstracts,
        "accepted_without_evidence": sum(
            1 for rec in accepted if not rec.get("relevance_evidence")
        ),
        "accepted_without_year": sum(1 for rec in accepted if not clean(rec.get("year"))),
        "accepted_missing_abstract": sum(
            1 for rec in accepted if rec.get("abstract_status") in (ABS_NONE, ABS_SYNTHETIC)
        ),
        "accepted_truncated_abstract": sum(
            1 for rec in accepted if rec.get("abstract_truncated")
        ),
        "accepted_topics": count_where(
            [
                {"topic": topic}
                for rec in accepted
                for topic in (rec.get("relevance_topics") or ["не определено"])
            ],
            "topic",
        ),
        "years_sources": count_where(accepted + review, "year_source"),
        "examples_rejected": sample(rejected),
        "examples_review": sample(review),
        "examples_subject_olympiad": sample(subject),
        "similar_unmerged_pairs": (similar_pairs or [])[:20],
        "similar_unmerged_total": len(similar_pairs or []),
    }


def public_projection(record: Mapping[str, Any]) -> dict[str, Any]:
    """Поля, необходимые интерфейсу. Без служебных подробностей."""
    keep = (
        "study_id",
        "title_original",
        "authors",
        "year",
        "year_source",
        "country",
        "document_type",
        "language",
        "category",
        "abstract_original",
        "abstract_ru",
        "abstract_status",
        "abstract_display",
        "container",
        "doi",
        "isbn",
        "url",
        "relevance_status",
        "relevance_reason",
        "relevance_evidence",
        "relevance_topics",
    )
    out = {key: record.get(key, "") for key in keep}
    if not out.get("relevance_evidence"):
        # Запись не может публиковаться без объяснения включения.
        out["relevance_evidence"] = [out.get("relevance_reason") or "Причина не указана"]
    return out


def write_outputs(
    accepted: list[dict],
    rejected: list[dict],
    review: list[dict],
    subject: list[dict],
    report: dict[str, Any],
    *,
    out_dir: Path | None = None,
    source: str = "build_dataset.py",
) -> None:
    out = out_dir or PUBLIC_DIR
    out.mkdir(parents=True, exist_ok=True)

    public_envelope = make_envelope(
        (public_projection(rec) for rec in accepted),
        source=source,
        extra={
            "catalog_name": "Олимпийский исследовательский портал",
            "visibility": "публичный каталог: только записи со статусом accepted",
            "review_count": len(review),
            "rejected_count": len(rejected),
            "subject_olympiad_count": len(subject),
            "relevance_policy": "accepted требует relevance_evidence",
        },
    )
    dump_envelope(public_envelope, out / "web_data.json")

    dump_envelope(
        make_envelope(review, source=source, extra={"note": "требуется ручная проверка"}),
        out / "review.json",
        indent=2,
    )
    dump_envelope(
        make_envelope(rejected, source=source, extra={"note": "отклонено как нерелевантное"}),
        out / "rejected.json",
        indent=2,
    )
    # Предметные олимпиады сохраняются отдельно: они не отклонены навсегда,
    # но и не являются Олимпийскими играми.
    subject_envelope = make_envelope(
        subject,
        source=source,
        extra={"note": "школьные/предметные олимпиады: не входят в публичный каталог"},
    )
    (out / "subject_olympiads.json").write_text(
        json.dumps(subject_envelope, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out / "relevance_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )



def run(
    records: Iterable[Mapping[str, Any]],
    *,
    out_dir: Path | None = None,
    source: str = "build_dataset.py",
) -> dict[str, Any]:
    """Полный проход сборки. Возвращает отчёт.

    Порядок важен:
      1. нормализация (идентификаторы, год, ОЧИСТКА аннотаций);
      2. структурная проверка — мусорные разделы не попадают в каталог;
      3. дедупликация;
      4. тематическая проверка (без заглушек вместо аннотаций);
      5. записи без подтверждённого года и без доказательств → review.
    """
    records = list(records)
    total_input = len(records)

    normalized = normalize_all(records)

    cleaned_abstracts = sum(1 for rec in normalized if rec.get("abstract_cleaned"))
    fake_removed = sum(1 for rec in normalized if rec.get("abstract_removed_fake"))

    unique, duplicates = deduplicate(normalized)

    accepted, rejected, review, subject = split_by_relevance(unique)

    # Структурный мусор исключается из публичного каталога, сомнительное — в review.
    reviewed_from_accepted = list(review)
    accepted_structural: list[dict] = []
    structure_rejected = 0
    for record in accepted:
        screen = record.get("doc_screen") or {}
        code = screen.get("code")
        if code == "reject":
            record["rejection_note"] = screen.get("reason", "")
            rejected.append(record)
            structure_rejected += 1
        elif code == "review":
            record["review_note"] = screen.get("reason", "")
            reviewed_from_accepted.append(record)
        else:
            accepted_structural.append(record)
    accepted = accepted_structural
    review = reviewed_from_accepted

    # Записи без подтверждённого года и без доказательств не публикуются.
    accepted_clean: list[dict] = []
    year_moved = 0
    evidence_moved = 0
    for record in accepted:
        if not clean(record.get("year")):
            record["review_note"] = record.get("year_reason") or "Год публикации не подтверждён"
            review.append(record)
            year_moved += 1
        elif not record.get("relevance_evidence"):
            record["review_note"] = "Нет подтверждений тематической связи"
            review.append(record)
            evidence_moved += 1
        else:
            accepted_clean.append(record)
    accepted = accepted_clean

    similar_pairs = find_similar_pairs(unique)

    report = build_relevance_report(
        accepted,
        rejected,
        review,
        subject,
        duplicates,
        total_input,
        fake_removed=fake_removed,
        cleaned_abstracts=cleaned_abstracts,
        similar_pairs=similar_pairs,
    )
    report["moved_to_review_by_year"] = year_moved
    report["moved_to_review_by_evidence"] = evidence_moved
    report["rejected_by_structure"] = structure_rejected
    report["status_summary"] = {
        "accepted": len(accepted),
        "rejected": len(rejected),
        "review": len(review),
        "subject_olympiad": len(subject),
    }

    write_outputs(accepted, rejected, review, subject, report, out_dir=out_dir, source=source)
    return report


def _load_source(path: Path) -> list[dict]:
    """Читает исходные записи: мастер-датасет CSV или JSON-конверт.

    Легаси-массив ``[{...}, ...]`` без ``metadata`` принимается только
    с явным предупреждением: такой файл не является актуальным
    публичным датасетом (его формирует ``scripts/build_master_dataset.py``).
    """
    if path.suffix.lower() == ".csv":
        return _load_csv(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        print(
            f"ВНИМАНИЕ: {path.name} — легаси-массив без контракта "
            "{metadata, data}. Актуальный источник — generated/master_dataset.csv. "
            "Данные будут обработаны, но формат следует привести к конверту.",
            file=sys.stderr,
        )
        return payload
    for key in ("data", "items", "records"):
        if isinstance(payload.get(key), list):
            return payload[key]
    raise SystemExit(f"Не удалось найти массив записей в {path}")


#: Переименование колонок мастер-датасета в поля записи каталога.
CSV_COLUMN_MAP: dict[str, str] = {
    "study_id": "study_id",
    "authors": "authors",
    "year": "year",
    "country": "country",
    "institution": "institution",
    "document_type": "document_type",
    "academic_level": "academic_level",
    "title_original": "title_original",
    "language": "language",
    "discipline": "discipline",
    "primary_topic": "primary_topic",
    "secondary_topic": "secondary_topic",
    "methodology": "methodology",
    "doi": "doi",
    "url": "url",
    "source": "source",
    "verification_status": "verification_status",
    "relevance": "relevance",
    "inclusion_reason": "inclusion_reason",
    "container": "container",
    "citation_count": "citation_count",
    "notes": "notes",
    "keywords": "keywords",
    "type": "type",
}


def _load_csv(path: Path) -> list[dict]:
    """Мастер-датасет хранится в cp1251 с разделителем «;»."""
    import csv

    for encoding in ("utf-8-sig", "cp1251", "utf-8"):
        try:
            with open(path, "r", encoding=encoding, newline="") as fh:
                sample = fh.read(4096)
                fh.seek(0)
                delimiter = ";" if sample.count(";") > sample.count(",") else ","
                reader = csv.DictReader(fh, delimiter=delimiter)
                rows = []
                for row in reader:
                    record: dict[str, Any] = {}
                    for column, value in row.items():
                        if column is None:
                            continue
                        key = CSV_COLUMN_MAP.get(column.strip(), column.strip())
                        record[key] = value
                    # Поле «Примечание» содержит аннотацию: это единственный
                    # текстовый источник, подтверждающий тематику.
                    note = clean(record.get("notes"))
                    if note and not record.get("summary"):
                        record["summary"] = note
                    record["abstract_original"] = clean(record.get("abstract_original")) or note
                    rows.append(record)
                return rows
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"Не удалось прочитать CSV: {path}")



def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Сборка каталога Olympic Research Hub")
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help="мастер-датасет (CSV) или JSON с записями",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=PUBLIC_DIR,
        help="каталог для результатов",
    )
    args = parser.parse_args(argv)

    if not args.input.exists():
        print(f"Источник не найден: {args.input}", file=sys.stderr)
        return 1

    records = _load_source(args.input)
    report = run(records, out_dir=args.out, source=f"build_dataset.py <- {args.input.name}")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

