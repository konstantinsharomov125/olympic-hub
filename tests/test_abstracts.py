"""Тесты очистки аннотаций."""

from olympic_abstracts import (
    ABS_NONE,
    ABS_PRESENT,
    ABS_SYNTHETIC,
    MISSING_MESSAGE,
    count_fake_abstracts,
    is_fake_abstract,
    sanitize_abstract_fields,
)


def test_synthetic_annotation_is_detected():
    assert is_fake_abstract("Научное исследование по теме олимпизма: Что-то")
    assert is_fake_abstract("Статья посвящена олимпийской тематике")


def test_real_annotation_is_not_flagged():
    real = (
        "This study examines the impact of Olympic education programmes on "
        "students' value orientations in secondary schools."
    )
    assert not is_fake_abstract(real)


def test_fake_annotation_removed_from_record():
    record = sanitize_abstract_fields(
        {"summary": "Научное исследование по теме олимпизма: Тестовая работа"}
    )
    assert record["abstract_original"] == ""
    assert record["abstract_status"] == ABS_SYNTHETIC
    assert record["abstract_display"] == MISSING_MESSAGE
    assert record["abstract_removed_fake"] is True


def test_real_annotation_preserved():
    original = "The article analyses the Olympic movement in the 21st century."
    record = sanitize_abstract_fields({"summary": original})
    assert record["abstract_original"] == original
    assert record["abstract_status"] == ABS_PRESENT
    assert record["abstract_display"] == original


def test_translation_marked_separately_from_original():
    record = sanitize_abstract_fields(
        {
            "summary": "The article analyses the Olympic movement.",
            "summary_ru": "В статье анализируется олимпийское движение.",
        }
    )
    assert record["abstract_original"] == "The article analyses the Olympic movement."
    assert record["abstract_ru"] == "В статье анализируется олимпийское движение."
    # Перевод не подменяет оригинал.
    assert record["abstract_original"] != record["abstract_ru"]


def test_translation_identical_to_original_is_dropped():
    text = "The article analyses the Olympic movement."
    record = sanitize_abstract_fields({"summary": text, "summary_ru": text})
    assert record["abstract_ru"] == ""


def test_missing_annotation_message():
    record = sanitize_abstract_fields({"summary": ""})
    assert record["abstract_status"] == ABS_NONE
    assert record["abstract_display"] == MISSING_MESSAGE


def test_count_fake_abstracts_on_dataset():
    records = [
        {"summary": "Научное исследование по теме олимпизма: Раз"},
        {"summary": "Настоящая аннотация о Олимпийских играх."},
        {"summary": "", "summary_ru": "Научное исследование по теме олимпизма: Два"},
    ]
    assert count_fake_abstracts(records) == 2
