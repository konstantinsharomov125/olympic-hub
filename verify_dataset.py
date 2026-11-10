"""Проверка целостности собранного каталога.

Запускается в CI перед публикацией и локально после сборки.
Возвращает код 1, если данные не годятся для публичного показа.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from olympic_abstracts import is_fake_abstract, is_placeholder  # noqa: E402
from olympic_citations import build_citation, is_forbidden_container  # noqa: E402
from olympic_hub_core import (  # noqa: E402
    check_year,
    clean,
    read_envelope,
    validate_envelope,
)
from olympic_screening import STRUCTURE_REJECT, screen_structure  # noqa: E402

PUBLIC = ROOT / "public" / "web_data.json"


def main() -> int:
    problems: list[str] = []

    if not PUBLIC.exists():
        print(f"Публичный каталог не найден: {PUBLIC}")
        return 1

    payload = json.loads(PUBLIC.read_text(encoding="utf-8"))
    problems += validate_envelope(payload)
    metadata, records = read_envelope(payload, strict=True)

    statuses = set()
    fake_count = 0
    stub_count = 0
    bad_year_count = 0
    empty_reason = 0
    no_evidence = 0
    structural = 0

    for record in records:
        record_id = record.get("study_id")
        status = record.get("relevance_status")
        statuses.add(status)
        if status != "accepted":
            problems.append(f"{record_id}: статус {status!r} в публичном каталоге")

        # Каждая принятая запись обязана объяснить своё включение.
        if not clean(record.get("relevance_reason")):
            empty_reason += 1
        if not record.get("relevance_evidence"):
            no_evidence += 1
            problems.append(f"{record_id}: нет relevance_evidence")

        # Служебные разделы книг в публичный каталог не допускаются.
        if screen_structure(record)["code"] == STRUCTURE_REJECT:
            structural += 1
            problems.append(f"{record_id}: служебная запись в публичном каталоге")

        display = clean(record.get("abstract_display"))
        if display and is_fake_abstract(display):
            fake_count += 1
        if display and is_placeholder(display):
            problems.append(f"{record_id}: заглушка вместо аннотации")

        if is_forbidden_container(record.get("container")):
            stub_count += 1

        # Неподтверждённый год не публикуется.
        if not clean(record.get("year")):
            bad_year_count += 1
            problems.append(f"{record_id}: опубликована без подтверждённого года")
            continue
        verdict = check_year(record.get("year"))
        if verdict.status != "ok":
            bad_year_count += 1
            problems.append(f"{record_id}: недопустимый год {verdict.year}")

        citation = build_citation(record)
        if "Научная публикация" in citation or "Unknown journal" in citation:
            problems.append(f"{record_id}: заглушка в ссылке")
        if "Автор не указан" in citation:
            problems.append(f"{record_id}: фиктивный автор в ссылке")

    print("Проверка публичного каталога")
    print(f"  записей: {len(records)}")
    print(f"  статусы: {sorted(s for s in statuses if s)}")
    print(f"  фиктивных аннотаций: {fake_count}")
    print(f"  заглушек источника: {stub_count}")
    print(f"  недопустимых/отсутствующих годов: {bad_year_count}")
    print(f"  записей без причины решения: {empty_reason}")
    print(f"  записей без relevance_evidence: {no_evidence}")
    print(f"  служебных записей: {structural}")
    print(f"  record_count в metadata: {metadata.get('record_count')}")

    if fake_count:
        problems.append(f"в публичных данных осталось фиктивных аннотаций: {fake_count}")
    if bad_year_count:
        problems.append(f"в публичных данных недопустимые годы: {bad_year_count}")

    if problems:
        print("\nОБНАРУЖЕНЫ ПРОБЛЕМЫ:")
        for item in problems[:40]:
            print(f"  - {item}")
        return 1

    print("\nПроверка пройдена: публичный каталог корректен.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
