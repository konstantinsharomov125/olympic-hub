"""Перевод аннотаций на русский язык.

Правила:
  * переводится только реальная аннотация из источника;
  * перевод пишется в отдельное поле ``abstract_ru`` и помечается как перевод;
  * оригинал в ``abstract_original`` не перезаписывается;
  * при ошибке перевода исходный текст остаётся, выдуманный текст не создаётся;
  * обрабатывается ограниченными пакетами, без отправки всего датасета сразу.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from olympic_abstracts import (  # noqa: E402
    ABS_AI,
    ABS_NONE,
    ABS_PRESENT,
    is_fake_abstract,
    is_placeholder,
)
from olympic_hub_core import clean, dump_envelope, read_envelope  # noqa: E402

MAX_CHARS = 4000
BATCH_SIZE = 20
REQUEST_TIMEOUT = 20
MAX_RETRIES = 2


def translate_text(text: str, translator) -> str | None:
    """Переводит фрагмент. Возвращает None при неудаче."""
    snippet = text[:MAX_CHARS]
    for attempt in range(MAX_RETRIES + 1):
        try:
            result = translator.translate(snippet)
            if result and result.strip() and result.strip() != snippet.strip():
                return result.strip()
            return None
        except Exception as exc:  # noqa: BLE001
            if attempt >= MAX_RETRIES:
                print(f"  ! перевод не выполнен: {type(exc).__name__}")
                return None
            time.sleep(2 * (attempt + 1))
    return None


def needs_translation(record: dict) -> bool:
    original = clean(record.get("abstract_original") or record.get("summary"))
    if not original or is_placeholder(original) or is_fake_abstract(original):
        return False
    existing = clean(record.get("abstract_ru"))
    if existing and existing != original:
        return False
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Перевод аннотаций")
    parser.add_argument("--input", type=Path, default=ROOT / "public" / "web_data.json")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=BATCH_SIZE, help="сколько записей обработать за запуск")
    args = parser.parse_args(argv)

    if not args.input.exists():
        print(f"Файл не найден: {args.input}", file=sys.stderr)
        return 1

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    metadata, records = read_envelope(payload, strict=False)

    candidates = [r for r in records if needs_translation(r)][: max(args.limit, 0)]
    if not candidates:
        print("Нет записей, требующих перевода.")
        return 0

    try:
        from deep_translator import GoogleTranslator
    except ImportError:
        print(
            "Библиотека deep-translator не установлена. "
            "Перевод пропущен, данные не изменены.",
            file=sys.stderr,
        )
        return 1

    translator = GoogleTranslator(source="auto", target="ru")
    translated_count = 0

    for index, record in enumerate(candidates, start=1):
        original = clean(record.get("abstract_original"))
        print(f"[{index}/{len(candidates)}] {clean(record.get('title_original'))[:60]}")
        result = translate_text(original, translator)
        if result:
            record["abstract_ru"] = result
            record["abstract_status"] = ABS_PRESENT
            record["abstract_display"] = result
            record["translation_status"] = "translated"
            record["translation_provider"] = "google-translate"
            translated_count += 1
        else:
            record.setdefault("translation_status", "unavailable")

    payload_out = {"metadata": metadata, "data": records}
    dump_envelope(payload_out, args.output or args.input, indent=None)
    print(f"Переведено записей: {translated_count} из {len(candidates)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
