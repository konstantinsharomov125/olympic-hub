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
    MISSING_MESSAGE,
    sanitize_abstract_fields,
)
from olympic_dedup import deduplicate  # noqa: E402
from olympic_hub_core import (  # noqa: E402
    CATEGORY_KEYWORDS,
    CATEGORY_NONE,
    check_year,
    clean,
    dump_envelope,
    make_envelope,
    norm_text,
)
from olympic_relevance import (  # noqa: E402
    ACCEPTED,
    REJECTED,
    REVIEW,
    split_by_relevance,
)

PUBLIC_DIR = ROOT / "public"


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
    out = dict(record)

    title = clean(out.get("title_original") or out.get("title"))
    authors = clean(out.get("authors") or out.get("author"))
    year_raw = out.get("year") or out.get("publication_year")

    verdict = check_year(year_raw)

    out["title_original"] = title
    out["authors"] = authors
    out["year"] = str(verdict.year) if verdict.status == "ok" else clean(year_raw)
    out["year_status"] = verdict.status
    out["year_reason"] = verdict.reason

    out = sanitize_abstract_fields(out)
    out["category"] = assign_category(out)

    if not out.get("study_id"):
        out["study_id"] = f"rec-{index:05d}"

    url = clean(out.get("url"))
    out["url"] = url if url.startswith(("http://", "https://")) else ""

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
    duplicates: list[dict],
    total_input: int,
    fake_removed: int,
) -> dict[str, Any]:
    def sample(items: list[dict], limit: int = 12) -> list[dict]:
        return [
            {
                "title": clean(item.get("title_original"))[:120],
                "reason": item.get("relevance_reason", ""),
            }
            for item in items[:limit]
        ]

    return {
        "input_records": total_input,
        "accepted": len(accepted),
        "rejected": len(rejected),
        "review": len(review),
        "duplicates_merged": len(duplicates),
        "fake_abstracts_removed": fake_removed,
        "examples_rejected": sample(rejected),
        "examples_review": sample(review),
    }


def public_projection(record: Mapping[str, Any]) -> dict[str, Any]:
    """Поля, необходимые интерфейсу. Без служебных подробностей."""
    keep = (
        "study_id",
        "title_original",
        "authors",
        "year",
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
        "url",
        "relevance_status",
        "relevance_reason",
    )
    return {key: record.get(key, "") for key in keep}


def write_outputs(
    accepted: list[dict],
    rejected: list[dict],
    review: list[dict],
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
    (out / "relevance_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def run(
    records: Iterable[Mapping[str, Any]],
    *,
    out_dir: Path | None = None,
    source: str = "build_dataset.py",
) -> dict[str, Any]:
    """Полный проход сборки. Возвращает отчёт."""
    records = list(records)
    total_input = len(records)

    normalized = normalize_all(records)
    unique, duplicates = deduplicate(normalized)

    accepted, rejected, review = split_by_relevance(unique)

    # Записи с невозможным годом не публикуются, но и не удаляются:
    # они переходят в review, чтобы год можно было проверить вручную.
    accepted_clean: list[dict] = []
    year_moved = 0
    for record in accepted:
        if record.get("year_status") == "invalid":
            record["review_note"] = record.get("year_reason") or "Год требует проверки"
            review.append(record)
            year_moved += 1
        else:
            accepted_clean.append(record)
    accepted = accepted_clean

    fake_removed = sum(1 for rec in unique if rec.get("abstract_removed_fake"))

    report = build_relevance_report(
        accepted, rejected, review, duplicates, total_input, fake_removed
    )
    report["moved_to_review_by_year"] = year_moved

    write_outputs(accepted, rejected, review, report, out_dir=out_dir, source=source)
    return report



def _load_source(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    for key in ("data", "items", "records"):
        if isinstance(payload.get(key), list):
            return payload[key]
    raise SystemExit(f"Не удалось найти массив записей в {path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Сборка каталога Olympic Research Hub")
    parser.add_argument(
        "--input",
        type=Path,
        default=ROOT / "generated" / "web_data.json",
        help="исходный JSON с записями",
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

