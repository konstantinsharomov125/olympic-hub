"""Регрессионные тесты на ошибки, выявленные независимым аудитом.

Каждый тест закрепляет конкретный класс ошибок из аудита, чтобы он не
вернулся при последующих изменениях фильтра, аннотаций или ссылок.
"""

from datetime import date

import pytest

from olympic_abstracts import (
    ABS_NONE,
    ABS_SYNTHETIC,
    MISSING_MESSAGE,
    sanitize_abstract_fields,
)
from olympic_citations import build_citation, split_authors
from olympic_dedup import deduplicate
from olympic_relevance import (
    ACCEPTED,
    REJECTED,
    REVIEW,
    SUBJECT_OLYMPIAD,
    assess_relevance,
)

MOMENT = date(2026, 11, 10)


# --------------------------------------------------------------------------
# 1. Имя автора не является олимпийским доказательством
# --------------------------------------------------------------------------


def test_olympiada_ivanova_author_is_not_evidence():
    """«Олимпиада Иванова» — имя человека, а не олимпийская тематика."""
    record = {
        "title_original": "Пособие по английскому языку для поступающих в лицей",
        "authors": "Олимпиада Иванова",
        "abstract_original": "Учебное пособие содержит тренировочные упражнения по грамматике.",
        "year": "2020",
    }
    decision = assess_relevance(record)
    assert decision.status != ACCEPTED
    assert decision.status in (REJECTED, REVIEW)


def test_author_name_olympiada_does_not_create_evidence():
    record = {
        "title_original": "Olympic Education in Secondary Schools",
        "authors": "Олимпиада Иванова",
        "abstract_original": "The paper analyses Olympic education in secondary schools.",
        "year": "2019",
    }
    decision = assess_relevance(record)
    assert decision.status == ACCEPTED
    joined = " ".join(decision.evidence)
    # Доказательство — название/аннотация, но не имя автора.
    assert "название" in joined or "аннотация" in joined
    assert "имена авторов" in joined


# --------------------------------------------------------------------------
# 2. «Движение» без олимпийского контекста
# --------------------------------------------------------------------------


def test_revolutionary_movement_is_not_olympic_movement():
    decision = assess_relevance(
        {
            "title_original": "Революционное движение 1870–1880-х гг. в освещении церковной периодики",
            "abstract_original": "Исследование посвящено освещению революционного движения в церковной печати.",
            "year": "2015",
        }
    )
    assert decision.status != ACCEPTED


def test_christian_student_movement_is_not_olympic():
    decision = assess_relevance(
        {
            "title_original": "Русское студенческое христианское движение на родине",
            "abstract_original": "Глава посвящена истории христианского студенческого движения.",
            "year": "2018",
        }
    )
    assert decision.status != ACCEPTED


# --------------------------------------------------------------------------
# 3. Школьные и предметные олимпиады
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "title",
    [
        "Школьная олимпиада по физике: задания и решения",
        "Олимпиада по математике для школьников",
        "The New Jersey Chemistry Olympics. A Competition for High School Science Students.",
        "Physics Olympics: Competitions for Secondary Physics Students",
        "A Spelling Olympics.",
    ],
)
def test_subject_olympiad_gets_its_own_status(title):
    decision = assess_relevance({"title_original": title, "year": "2010"})
    assert decision.status == SUBJECT_OLYMPIAD
    assert decision.status != ACCEPTED


def test_real_olympic_games_not_mistaken_for_subject_olympiad():
    decision = assess_relevance(
        {
            "title_original": "Olympic Games and school sport: the legacy for pupils",
            "abstract_original": "The article studies how the Olympic Games influenced school sport.",
            "year": "2019",
        }
    )
    assert decision.status == ACCEPTED


# --------------------------------------------------------------------------
# 4. Статья по химии не принимается из-за случайного упоминания
# --------------------------------------------------------------------------


def test_chemistry_article_with_incidental_olympic_mention_rejected():
    """Название — химия, олимпийские слова только в аннотации: не принимаем."""
    decision = assess_relevance(
        {
            "title_original": "Фазовые равновесия в трехкомпонентных солевых системах LiBr-Li2CO3",
            "abstract_original": (
                "Изучены фазовые равновесия солевых систем. Образцы отбирали вблизи "
                "олимпийских объектов, упоминаемых в отчёте о строительстве."
            ),
            "year": "2019",
        }
    )
    assert decision.status != ACCEPTED


def test_geochemistry_with_olympic_context_rejected():
    decision = assess_relevance(
        {
            "title_original": "Metal geochemistry in bottom sediments from an urbanized estuary",
            "abstract_original": (
                "Sediment geochemistry near the Olympic Games venue shows sodium and "
                "sulfate contamination from dredging works."
            ),
            "year": "2020",
        }
    )
    assert decision.status == REJECTED


def test_occupational_heat_article_rejected():
    decision = assess_relevance(
        {
            "title_original": "Leveraging wearables to safeguard workers in a hotter climate",
            "abstract_original": (
                "Occupational heat illness among workers is growing. Experiences from recent "
                "Olympic Games showed monitoring systems can operate in extreme heat."
            ),
            "year": "2024",
        }
    )
    assert decision.status == REJECTED


# --------------------------------------------------------------------------
# 5. Отсутствие аннотации не компенсируется выдуманным доказательством
# --------------------------------------------------------------------------


def test_synthetic_abstract_removed_and_not_used_as_evidence():
    record = sanitize_abstract_fields(
        {
            "title_original": "Глава 6 Русское студенческое христианское движение на родине",
            "summary": "Научное исследование по теме олимпизма: 'Глава 6 …'.",
            "year": "2018",
        }
    )
    assert record["abstract_status"] == ABS_SYNTHETIC
    assert record["abstract_original"] == ""
    # Даже с очищенной аннотацией запись не проходит.
    assert assess_relevance(record).status != ACCEPTED


def test_missing_abstract_does_not_produce_acceptance_for_unrelated_title():
    record = sanitize_abstract_fields(
        {"title_original": "Инструкция по охране труда для работников склада", "year": "2021"}
    )
    assert record["abstract_status"] == ABS_NONE
    assert record["abstract_display"] == MISSING_MESSAGE
    assert assess_relevance(record).status != ACCEPTED


# --------------------------------------------------------------------------
# 6. Структурные записи не попадают в accepted
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "title",
    ["Frontmatter", "Contents", "Index", "Illustrations", "Bibliography",
     "Acknowledgements", "List of Abbreviations", "Содержание"],
)
def test_structural_titles_are_never_accepted(title):
    from olympic_screening import STRUCTURE_REJECT, screen_structure

    verdict = screen_structure({"title_original": title})
    assert verdict["code"] == STRUCTURE_REJECT, title


def test_chapter_title_with_real_content_is_not_discarded():
    from olympic_screening import STRUCTURE_OK, screen_structure

    verdict = screen_structure(
        {
            "title_original": "Глава 6 Русское студенческое христианское движение на родине",
            "abstract_original": "Настоящая аннотация главы о студенческом движении.",
            "container": "Сборник статей",
        }
    )
    assert verdict["code"] == STRUCTURE_OK


def test_structural_record_does_not_reach_public_catalog(tmp_path):
    import json

    from build_dataset import run

    records = [
        {
            "study_id": "s1",
            "title_original": "Contents",
            "abstract_original": "Olympic Games in contents of a book about sport.",
            "year": "2015",
        }
    ]
    run(records, out_dir=tmp_path, source="test")
    public = json.loads((tmp_path / "web_data.json").read_text(encoding="utf-8"))
    assert public["data"] == []


# --------------------------------------------------------------------------
# 7. Разбор авторов с несколькими инициалами и без фиктивного автора
# --------------------------------------------------------------------------


def test_multiple_initials_parsed_as_single_author():
    authors = split_authors("Финогенов А. А., Е. И. Фролов")
    assert authors == ["Финогенов А. А.", "Е. И. Фролов"]


def test_comma_inside_author_name_is_not_a_separator():
    authors = split_authors("Фамилия, И. О.; Другая, П. К.")
    assert len(authors) == 2
    assert authors[0].startswith("Фамилия")


def test_latin_authors_split_by_comma():
    authors = split_authors("Gogovor A., Savoie M., Moride Y., Krelenbaum M., Montague T.")
    assert authors == ["Gogovor A.", "Savoie M.", "Moride Y.", "Krelenbaum M.", "Montague T."]


def test_multiword_cyrillic_names_are_separate_authors():
    authors = split_authors("Таджиева Сахыджемал, Велмаммедов Оразмаммет")
    assert len(authors) == 2


def test_citation_without_author_has_no_fake_author():
    citation = build_citation(
        {"title_original": "Olympic Movement Overview", "year": "2015"}, moment=MOMENT
    )
    assert citation.startswith("Olympic Movement Overview")
    for stub in ("Автор не указан", "Неизвестный автор", "None", "unknown"):
        assert stub not in citation


def test_placeholder_author_is_treated_as_absent():
    assert split_authors("Автор не указан") == []
    citation = build_citation(
        {"title_original": "Олимпийское наследие", "authors": "Автор не указан", "year": "2019"},
        moment=MOMENT,
    )
    assert "Автор не указан" not in citation


def test_citation_keeps_container_and_year():
    citation = build_citation(
        {
            "title_original": "Contemporary Disease Management in Quebec",
            "authors": "Gogovor A., Savoie M.",
            "container": "Healthcare Quarterly",
            "year": "2008",
            "url": "https://example.org/article",
        },
        moment=MOMENT,
    )
    assert "// Healthcare Quarterly" in citation
    assert ". – 2008." in citation


# --------------------------------------------------------------------------
# 8. DOI не искажается
# --------------------------------------------------------------------------


def test_doi_is_preserved_verbatim_in_citation():
    citation = build_citation(
        {
            "title_original": "Fair Play and Olympic Ethics",
            "authors": "Smith J.",
            "year": "2015",
            "doi": "10.5555/fairplay",
        },
        moment=MOMENT,
    )
    assert "https://doi.org/10.5555/fairplay" in citation


def test_nonstandard_but_valid_url_is_kept_when_no_doi():
    citation = build_citation(
        {
            "title_original": "Olympic Studies",
            "year": "2020",
            "url": "https://openalex.org/W7217958946",
        },
        moment=MOMENT,
    )
    assert "https://openalex.org/W7217958946" in citation


# --------------------------------------------------------------------------
# 9. Дубликаты: похожие названия не сливаются без оснований
# --------------------------------------------------------------------------


def test_same_title_different_year_is_not_merged():
    records = [
        {"study_id": "a", "title_original": "Olympic Education in Modern Schools",
         "authors": "Ivanov I.", "year": "2019"},
        {"study_id": "b", "title_original": "Olympic Education in Modern Schools",
         "authors": "Ivanov I.", "year": "2021"},
    ]
    unique, merged = deduplicate(records)
    assert len(unique) == 2
    assert merged == []


def test_homoglyph_titles_are_recognised_as_duplicates():
    """«АКТУАЛЬНЫЕ» с латинской T — тот же текст, что и кириллический."""
    records = [
        {"study_id": "a", "title_original": "АКТУАЛЬНЫЕ ПРОБЛЕМЫ ОЛИМПИЙСКОГО ОБРАЗОВАНИЯ",
         "authors": "Иванов И.", "year": "2019"},
        {"study_id": "b", "title_original": "АКTУАЛЬНЫЕ ПРОБЛЕМЫ ОЛИМПИЙСКОГО ОБРАЗОВАНИЯ",
         "authors": "Иванов И.", "year": "2019"},
    ]
    unique, merged = deduplicate(records)
    assert len(unique) == 1
    assert len(merged) == 1


# --------------------------------------------------------------------------
# 10. Записи с неподтверждённым годом не публикуются
# --------------------------------------------------------------------------


def test_unconfirmed_year_is_not_published(tmp_path):
    import json

    from build_dataset import run

    records = [
        {"study_id": "g1", "title_original": "Olympic Games Legacy in Sochi",
         "abstract_original": "The Olympic legacy of the Sochi Games.", "year": "NR"},
        {"study_id": "g2", "title_original": "Olympic Education in Schools",
         "abstract_original": "Olympic education at schools.", "year": "2115"},
    ]
    run(records, out_dir=tmp_path, source="test")
    public = json.loads((tmp_path / "web_data.json").read_text(encoding="utf-8"))
    published = {r["study_id"] for r in public["data"]}
    assert "g1" not in published  # год не указан
    assert "g2" not in published  # невозможный год
    for record in public["data"]:
        assert record["year"], "у опубликованной записи обязан быть подтверждённый год"


# --------------------------------------------------------------------------
# 11. У каждой принятой записи есть relevance_evidence
# --------------------------------------------------------------------------


def test_every_accepted_record_has_evidence():
    samples = [
        {"title_original": "Olympic Education in Schools", "year": "2019",
         "abstract_original": "Olympic education in schools."},
        {"title_original": "История Олимпийских игр", "year": "2015"},
        {"title_original": "Paralympic Games media coverage", "year": "2020",
         "abstract_original": "Coverage of Paralympic Games."},
    ]
    for sample in samples:
        decision = assess_relevance(sample)
        assert decision.status == ACCEPTED, sample
        assert decision.evidence, f"нет доказательств для {sample}"


def test_public_catalog_records_all_have_evidence(tmp_path):
    import json

    from build_dataset import run

    records = [
        {"study_id": "e1", "title_original": "Olympic Education in Schools",
         "abstract_original": "Olympic education in schools.", "year": "2019"},
        {"study_id": "e2", "title_original": "Олимпийское наследие Сочи", "year": "2016"},
    ]
    run(records, out_dir=tmp_path, source="test")
    public = json.loads((tmp_path / "web_data.json").read_text(encoding="utf-8"))
    assert public["data"], "ожидались принятые записи"
    for record in public["data"]:
        assert record["relevance_evidence"], record["study_id"]
        assert record["relevance_status"] == "accepted"
