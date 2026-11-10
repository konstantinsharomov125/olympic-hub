"""Классификация направлений через Gemini (необязательный режим).

Требования:
  * ключ читается только из ``GEMINI_API_KEY``;
  * интерактивный запрос ключа запрещён — в CI это невозможно;
  * при отсутствии ключа скрипт сообщает об этом и завершается без ошибки;
  * AI не принимает решение о научной релевантности: только уточняет
    направление уже принятых записей, и результат помечается методом.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from olympic_hub_core import CATEGORIES, dump_envelope, read_envelope  # noqa: E402

KEY_ENV_VAR = "GEMINI_API_KEY"
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
MAX_RETRIES = 3
BATCH_DEFAULT = 10

PROMPT_TEMPLATE = """Ты помогаешь классифицировать научные публикации об олимпизме.

Выбери ОДНО направление строго из списка:
{category_list}

Если ни одно не подходит, ответь: {fallback}

Название: {title}
Аннотация: {summary}

Ответь только названием направления."""


def build_prompt(title: str, summary: str) -> str:
    return PROMPT_TEMPLATE.format(
        category_list="\n".join(f"- {c}" for c in CATEGORIES),
        fallback=CATEGORIES[-1],
        title=title or "не указано",
        summary=(summary or "аннотация отсутствует")[:400],
    )


def classify(client, title: str, summary: str) -> str | None:
    prompt = build_prompt(title, summary)
    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
            text = (response.text or "").strip().strip('"\'')
            for category in CATEGORIES:
                if category.lower() in text.lower():
                    return category
            return None
        except Exception as exc:  # noqa: BLE001
            message = str(exc)
            if "429" in message or "RESOURCE_EXHAUSTED" in message:
                wait = 10 * (attempt + 1)
                print(f"  лимит запросов, пауза {wait} с")
                time.sleep(wait)
                continue
            if attempt >= MAX_RETRIES - 1:
                print(f"  ошибка запроса: {type(exc).__name__}")
                return None
            time.sleep(3)
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Уточнение направлений через Gemini")
    parser.add_argument("--input", type=Path, default=ROOT / "public" / "web_data.json")
    parser.add_argument("--limit", type=int, default=BATCH_DEFAULT)
    args = parser.parse_args(argv)

    api_key = (os.getenv(KEY_ENV_VAR) or "").strip()
    if not api_key:
        print(
            f"AI-классификация недоступна: переменная {KEY_ENV_VAR} не задана. "
            "Данные не изменены.",
            file=sys.stderr,
        )
        return 0

    try:
        from google import genai
    except ImportError:
        print("Библиотека google-genai не установлена. AI-классификация пропущена.", file=sys.stderr)
        return 0

    if not args.input.exists():
        print(f"Файл не найден: {args.input}", file=sys.stderr)
        return 1

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    metadata, records = read_envelope(payload, strict=False)

    from olympic_hub_core import CATEGORY_NONE

    targets = [r for r in records if r.get("category") in (None, "", CATEGORY_NONE)][
        : max(args.limit, 0)
    ]
    if not targets:
        print("Нет записей без направления — уточнение не требуется.")
        return 0

    client = genai.Client(api_key=api_key)
    updated = 0

    for index, record in enumerate(targets, start=1):
        title = record.get("title_original", "")
        summary = record.get("abstract_original") or record.get("abstract_ru") or ""
        print(f"[{index}/{len(targets)}] {title[:60]}")
        category = classify(client, title, summary)
        if category and category != CATEGORY_NONE:
            record["category"] = category
            record["category_method"] = f"ai:{MODEL_NAME}"
            updated += 1
            print(f"  -> {category}")
        time.sleep(1.5)

    dump_envelope({"metadata": metadata, "data": records}, args.input)
    print(f"Уточнено записей: {updated} из {len(targets)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
