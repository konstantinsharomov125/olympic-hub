#!/usr/bin/env python3
"""
Build Olympic Research Hub derived data from the published Google Sheets CSV.

Input:
  GOOGLE_SHEETS_CSV_URL env var, or the default URL below.

Outputs:
  generated/raw_data.csv
  generated/master_dataset.csv
  generated/web_data.json
  generated/data_quality_report.csv

The source is never edited in place.
"""

from __future__ import annotations
import csv
import io
import json
import os
import re
import sys
import unicodedata
import urllib.request
from collections import Counter
from pathlib import Path

DEFAULT_URL = (
    "https://docs.google.com/spreadsheets/d/e/"
    "2PACX-1vSxNFzNuMUtkeLmD7i8VVSA8vLYqtRE4WrIeqS_BM3UmMBSwz93mEs_EXav9F5LAw/"
    "pub?gid=1083555527&single=true&output=csv"
)

EXPECTED_FIELDS = [
    "ID","Автор","Год","Страна","Университет / организация","Тип документа",
    "Уровень","Название (оригинал)","Язык","Научная дисциплина",
    "Основное направление","Вторичное направление","Методология","DOI","URL",
    "Источник","Статус верификации","Уровень релевантности","Причина включения",
    "Контейнер (журнал/издательство)","Цитируемость","Примечание"
]

CANONICAL = {
    "ID":"study_id","Автор":"authors","Год":"year","Страна":"country",
    "Университет / организация":"institution","Тип документа":"document_type",
    "Уровень":"academic_level","Название (оригинал)":"title_original",
    "Язык":"language","Научная дисциплина":"discipline",
    "Основное направление":"primary_topic","Вторичное направление":"secondary_topic",
    "Методология":"methodology","DOI":"doi","URL":"url","Источник":"source",
    "Статус верификации":"verification_status",
    "Уровень релевантности":"relevance","Причина включения":"inclusion_reason",
    "Контейнер (журнал/издательство)":"container","Цитируемость":"citation_count",
    "Примечание":"notes"
}

def clean(v: object) -> str:
    return str(v or "").replace("\ufeff", "").strip()

def norm_text(s: str) -> str:
    s = unicodedata.normalize("NFKC", clean(s)).lower().replace("ё", "е")
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^\w\s]", " ", s, flags=re.UNICODE)
    return re.sub(r"\s+", " ", s).strip()

def norm_doi(s: str) -> str:
    s = clean(s).lower()
    s = re.sub(r"^https?://(dx\.)?doi\.org/", "", s)
    s = re.sub(r"^doi:\s*", "", s)
    return s.rstrip(" .;,/")

def fetch(url: str) -> bytes:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "OlympicResearchHub-data-builder/1.0"}
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()

def parse_csv(raw: bytes) -> list[dict[str, str]]:
    text = raw.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ValueError("CSV has no header row")
    headers = [clean(x) for x in reader.fieldnames]
    missing = [f for f in EXPECTED_FIELDS if f not in headers]
    if missing:
        raise ValueError("Missing expected fields: " + "; ".join(missing))
    rows = []
    for row in reader:
        clean_row = {clean(k): clean(v) for k, v in row.items()}
        if any(clean(v) for v in clean_row.values()):
            rows.append(clean_row)
    return rows

def to_master(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    out = []
    for r in rows:
        m = {CANONICAL[k]: clean(r.get(k, "")) for k in EXPECTED_FIELDS}
        m["doi_normalized"] = norm_doi(m["doi"])
        m["title_normalized"] = norm_text(m["title_original"])
        m["author_normalized"] = norm_text(m["authors"])
        try:
            m["year_numeric"] = int(m["year"])
        except Exception:
            m["year_numeric"] = ""
        try:
            m["citation_count"] = int(re.sub(r"[^\d-]", "", m["citation_count"])) if m["citation_count"] else 0
        except Exception:
            m["citation_count"] = 0
        out.append(m)
    return out

def quality_report(rows: list[dict[str, str]]) -> list[list[object]]:
    n = len(rows)
    report = [["metric", "value", "notes"]]
    report.append(["records", n, "Rows with at least one non-empty field"])
    ids = [r["study_id"] for r in rows if r["study_id"]]
    report.append(["missing_id", sum(not x for x in ids), "Should be 0"])
    report.append(["duplicate_id", n - len(set(ids)), "Should be 0"])
    report.append(["missing_title", sum(not r["title_original"] for r in rows), "Should be reviewed"])
    report.append(["missing_year", sum(not re.fullmatch(r"\d{4}", r["year"]) for r in rows), "Should be reviewed"])
    report.append(["doi_present", sum(bool(r["doi_normalized"]) for r in rows), "DOI after normalization"])
    report.append(["url_present", sum(bool(r["url"]) for r in rows), "URL present"])
    report.append(["methodology_ne_or_blank",
                   sum((not r["methodology"]) or norm_text(r["methodology"]) == "ne" for r in rows),
                   "Do not infer missing methodology"])
    report.append(["relevance_r1", sum(norm_text(r["relevance"]) == "r1" for r in rows), "Current coding"])
    report.append(["relevance_r2", sum(norm_text(r["relevance"]) == "r2" for r in rows), "Current coding"])
    return report

def web_projection(master: list[dict[str, str]]) -> list[dict[str, object]]:
    # Compact projection used by the website.
    keep = [
        "study_id","authors","year_numeric","country","institution","document_type",
        "academic_level","title_original","language","discipline","primary_topic",
        "secondary_topic","methodology","doi","doi_normalized","url","source",
        "verification_status","relevance","inclusion_reason","container","citation_count","notes"
    ]
    return [{k: row.get(k, "") for k in keep} for row in master]

def main() -> int:
    root = Path(__file__).resolve().parents[1]
    out_dir = root / "generated"
    out_dir.mkdir(parents=True, exist_ok=True)

    url = os.environ.get("GOOGLE_SHEETS_CSV_URL", DEFAULT_URL)
    raw = fetch(url)
    rows = parse_csv(raw)
    master = to_master(rows)

    (out_dir / "raw_data.csv").write_bytes(raw)

    with (out_dir / "master_dataset.csv").open("w", newline="", encoding="utf-8-sig") as f:
        fields = list(master[0].keys()) if master else list(CANONICAL.values())
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(master)

    from datetime import datetime, timezone
    web_payload = {
        "metadata": {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "record_count": len(master),
            "source": "published Google Sheets CSV"
        },
        "data": web_projection(master)
    }
    with (out_dir / "web_data.json").open("w", encoding="utf-8") as f:
        json.dump(web_payload, f, ensure_ascii=False, separators=(",", ":"))

    with (out_dir / "data_quality_report.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerows(quality_report(master))

    print(f"Built {len(master):,} records from Google Sheets")
    print(f"Output directory: {out_dir}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
