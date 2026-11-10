"""Сбор и подготовка записей каталога.

Скрипт больше не перезаписывает JSON массивом: единая сборка выполняется
через ``build_dataset.py``. Здесь остаётся только безопасная подготовка
исходного файла — чтение по контракту и запись в тот же контракт.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from olympic_hub_core import dump_envelope, make_envelope, read_envelope  # noqa: E402

DEFAULT_INPUT = ROOT / "generated" / "web_data.json"


def load_records(path: Path) -> list[dict]:
    """Читает записи, принимая и новый конверт, и старый массив."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    _, records = read_envelope(payload, strict=False)
    return records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Подготовка исходных записей каталога")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_INPUT)
    args = parser.parse_args(argv)

    if not args.input.exists():
        print(f"Файл не найден: {args.input}", file=sys.stderr)
        return 1

    records = load_records(args.input)
    envelope = make_envelope(
        records,
        source=f"auto_collector.py <- {args.input.name}",
        extra={"note": "промежуточный файл; публичная сборка — build_dataset.py"},
    )
    dump_envelope(envelope, args.output)
    print(f"Записей подготовлено: {len(records)} -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
