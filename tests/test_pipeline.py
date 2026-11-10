"""Интеграционные тесты сборки каталога и безопасности."""

import json
import re
from pathlib import Path

from build_dataset import run

ROOT = Path(__file__).resolve().parents[1]


def _records():
    return [
        {
            "study_id": "1",
            "title_original": "Olympic Education and Values in Schools",
            "authors": "Иванов П. С.",
            "year": "2019",
            "summary": "Научное исследование по теме олимпизма: выдуманный текст",
        },
        {
            "study_id": "2",
            "title_original": "Breaking the obesity-cancer link in European schools",
            "year": "2021",
            "summary": "Real abstract about obesity prevention and cancer risk.",
        },
        {
            "study_id": "3",
            "title_original": "Olympic Games Legacy in Sochi",
            "year": "2115",
            "summary": "Real abstract about the Olympic legacy of the Sochi Games.",
        },
    ]


def test_pipeline_outputs(tmp_path):
    report = run(_records(), out_dir=tmp_path, source="test")

    # Публичный каталог содержит только accepted.
    public = json.loads((tmp_path / "web_data.json").read_text(encoding="utf-8"))
    assert public["metadata"]["record_count"] == len(public["data"])
    assert all(r["relevance_status"] == "accepted" for r in public["data"])

    # Оффтопик отклонён.
    rejected = json.loads((tmp_path / "rejected.json").read_text(encoding="utf-8"))
    assert any(r["study_id"] == "2" for r in rejected["data"])

    # Запись с невозможным годом не публикуется, но сохраняется в review.
    review = json.loads((tmp_path / "review.json").read_text(encoding="utf-8"))
    review_ids = {r["study_id"] for r in review["data"]}
    assert "3" in review_ids
    assert all(r["study_id"] != "3" for r in public["data"])

    assert report["moved_to_review_by_year"] == 1


def test_no_fake_annotation_in_public_output(tmp_path):
    run(_records(), out_dir=tmp_path, source="test")
    public = json.loads((tmp_path / "web_data.json").read_text(encoding="utf-8"))
    for record in public["data"]:
        display = record.get("abstract_display") or ""
        assert "Научное исследование по теме" not in display


def test_public_catalog_has_no_forbidden_stubs(tmp_path):
    run(_records(), out_dir=tmp_path, source="test")
    public = json.loads((tmp_path / "web_data.json").read_text(encoding="utf-8"))
    for record in public["data"]:
        container = (record.get("container") or "").lower()
        assert container not in {"научная публикация", "unknown journal", "n/a"}


def test_no_hardcoded_vk_token_in_sources():
    """В коде не должно быть токенов вида vk1.a...."""
    pattern = re.compile(r"vk1\.a\.[A-Za-z0-9_-]{20,}")
    checked = list(ROOT.glob("*.py")) + list(ROOT.glob("scripts/*.py"))
    checked += list(ROOT.glob(".github/workflows/*.yml"))

    offenders = []
    for path in checked:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if pattern.search(text):
            offenders.append(path.name)

    assert offenders == [], f"найдены токены в файлах: {offenders}"


def test_vk_bot_requires_environment_token():
    """Бот не должен иметь значения токена по умолчанию."""
    text = (ROOT / "scripts" / "vk_bot.py").read_text(encoding="utf-8")
    assert "VK_GROUP_TOKEN" in text
    assert "VkBotLongPoll" in text
    # Нет подстановки значения по умолчанию.
    assert "os.getenv(\"VK_GROUP_TOKEN\", \"vk" not in text
