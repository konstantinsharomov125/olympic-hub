"""Тесты проверки годов, дублей и контракта данных."""

import pytest

from olympic_dedup import deduplicate
from olympic_hub_core import (
    DataContractError,
    check_year,
    make_envelope,
    norm_doi,
    read_envelope,
    validate_envelope,
)

CURRENT = 2026


def test_valid_year_ok():
    assert check_year("2008", current_year=CURRENT).status == "ok"
    assert check_year("2008", current_year=CURRENT).year == 2008


def test_future_year_is_invalid():
    verdict = check_year("2115", current_year=CURRENT)
    assert verdict.status == "invalid"
    assert "будущем" in verdict.reason


def test_year_before_olympic_games_is_invalid():
    assert check_year("1850", current_year=CURRENT).status == "invalid"


def test_missing_year_goes_to_review():
    verdict = check_year("", current_year=CURRENT)
    assert verdict.status == "review"
    assert verdict.year is None


def test_unparseable_year_goes_to_review():
    assert check_year("неизвестно", current_year=CURRENT).status == "review"


def test_year_is_not_silently_corrected():
    """Невозможный год не подменяется правдоподобным."""
    verdict = check_year("2200", current_year=CURRENT)
    assert verdict.year == 2200
    assert verdict.status == "invalid"


def test_envelope_roundtrip():
    envelope = make_envelope([{"study_id": "1"}], source="test")
    metadata, records = read_envelope(envelope)
    assert metadata["record_count"] == 1
    assert records == [{"study_id": "1"}]


def test_array_root_rejected_in_strict_mode():
    with pytest.raises(DataContractError):
        read_envelope([{"study_id": "1"}], strict=True)


def test_legacy_array_readable_in_lenient_mode():
    _, records = read_envelope([{"study_id": "1"}], strict=False)
    assert len(records) == 1


def test_validate_envelope_detects_count_mismatch():
    envelope = make_envelope([{"study_id": "1"}], source="test")
    envelope["metadata"]["record_count"] = 5
    problems = validate_envelope(envelope)
    assert any("record_count" in p for p in problems)


def test_validate_envelope_ok():
    envelope = make_envelope([{"study_id": "1"}], source="test")
    assert validate_envelope(envelope) == []


def test_norm_doi_handles_url_and_prefix():
    assert norm_doi("https://doi.org/10.1234/ABC") == "10.1234/abc"
    assert norm_doi("doi:10.1234/abc.") == "10.1234/abc"


def test_dedup_by_doi():
    records = [
        {"study_id": "a", "doi": "10.1/x", "title_original": "First"},
        {"study_id": "b", "doi": "https://doi.org/10.1/X", "title_original": "Second"},
    ]
    unique, merged = deduplicate(records)
    assert len(unique) == 1
    assert len(merged) == 1
    assert "b" in unique[0]["merged_from"]


def test_dedup_by_title_author_year():
    records = [
        {
            "study_id": "a",
            "title_original": "Olympic Education in Modern Schools",
            "authors": "Ivanov I.",
            "year": "2019",
        },
        {
            "study_id": "b",
            "title_original": "Olympic education in modern schools",
            "authors": "Ivanov I.",
            "year": "2019",
        },
    ]
    unique, merged = deduplicate(records)
    assert len(unique) == 1
    assert len(merged) == 1


def test_dedup_does_not_merge_similar_titles_with_different_authors():
    records = [
        {
            "study_id": "a",
            "title_original": "Olympic Education in Modern Schools",
            "authors": "Ivanov I.",
            "year": "2019",
        },
        {
            "study_id": "b",
            "title_original": "Olympic Education in Modern Schools",
            "authors": "Petrov P.",
            "year": "2019",
        },
    ]
    unique, merged = deduplicate(records)
    assert len(unique) == 2
    assert merged == []


def test_dedup_preserves_source_information():
    records = [
        {"study_id": "a", "doi": "10.1/x", "title_original": "One", "url": "https://a"},
        {"study_id": "b", "doi": "10.1/x", "title_original": "One", "url": "https://b"},
    ]
    unique, _ = deduplicate(records)
    assert unique[0]["url"] == "https://a"
    assert "https://b" in unique[0]["source_urls"]
