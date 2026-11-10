"""Тесты генератора библиографических ссылок."""

from datetime import date

from olympic_citations import build_citation, format_access_date

MOMENT = date(2026, 11, 10)


def test_gogovor_five_authors_full_structure(gogovor_record):
    citation = build_citation(gogovor_record, moment=MOMENT)

    # Первый автор: фамилия и инициалы.
    assert citation.startswith("Gogovor A. Contemporary Disease Management in Quebec")
    # Остальные авторы после косой черты в форме «И. Фамилия».
    assert "/ M. Savoie, Y. Moride, M. Krelenbaum, T. Montague" in citation
    # Реальный журнал, а не заглушка.
    assert "// Healthcare Quarterly" in citation
    # Год публикации.
    assert ". – 2008." in citation
    # Дата обращения вычисляется автоматически.
    assert "(дата обращения: 10.11.2026)" in citation
    # Никаких заглушек.
    assert "Научная публикация" not in citation
    assert "Unknown journal" not in citation


def test_single_author():
    record = {
        "title_original": "Olympic Education in Schools",
        "authors": "Иванов П. С.",
        "container": "Теория и практика физической культуры",
        "year": "2019",
    }
    citation = build_citation(record, moment=MOMENT)
    assert "Иванов П.С." in citation
    assert " / " not in citation  # второго автора нет
    assert "// Теория и практика физической культуры" in citation
    assert "2019" in citation



def test_without_container():
    record = {
        "title_original": "Олимпийское наследие Сочи",
        "authors": "Петрова А. В.",
        "year": "2021",
    }
    citation = build_citation(record, moment=MOMENT)
    assert "//" not in citation
    assert "2021" in citation
    assert citation.startswith("Петрова А.В.")


def test_with_doi():
    record = {
        "title_original": "Fair Play and Olympic Ethics",
        "authors": "Smith J.",
        "year": "2015",
        "doi": "10.5555/fairplay",
    }
    citation = build_citation(record, moment=MOMENT)
    assert "https://doi.org/10.5555/fairplay" in citation


def test_incomplete_record_without_author_and_year():
    record = {"title_original": "Olympic Movement Overview"}
    citation = build_citation(record, moment=MOMENT)
    # Ссылка остаётся честной: нет выдуманного автора, года и журнала.
    assert "Olympic Movement Overview" in citation
    assert "None" not in citation
    assert "Научная публикация" not in citation


def test_forbidden_container_is_dropped():
    record = {
        "title_original": "Olympic Charter Analysis",
        "authors": "Ivanov I.",
        "container": "Unknown journal",
        "year": "2018",
    }
    citation = build_citation(record, moment=MOMENT)
    assert "Unknown journal" not in citation


def test_access_date_is_computed_not_hardcoded():
    assert format_access_date(date(2026, 11, 10)) == "10.11.2026"
    assert format_access_date(date(2027, 1, 5)) == "05.01.2027"

    record = {
        "title_original": "Olympic Studies",
        "year": "2020",
        "url": "https://example.org/olympic-studies",
    }
    first = build_citation(record, moment=date(2026, 11, 10))
    second = build_citation(record, moment=date(2030, 3, 7))
    assert "10.11.2026" in first
    assert "07.03.2030" in second
    assert first != second
    # Старая захардкоженная дата больше не появляется.
    assert "11.10.2026" not in second



def test_publication_year_not_confused_with_access_year():
    record = {
        "title_original": "Olympic Legacy",
        "year": "1998",
        "url": "https://example.org/legacy",
    }
    citation = build_citation(record, moment=date(2026, 11, 10))
    assert ". – 1998." in citation
    assert "(дата обращения: 10.11.2026)" in citation



def test_future_year_not_used_as_publication_year():
    record = {"title_original": "Olympic Legacy", "year": "2115"}
    citation = build_citation(record, moment=MOMENT)
    # Невозможный год не попадает в ссылку как год публикации.
    assert "2115" not in citation
