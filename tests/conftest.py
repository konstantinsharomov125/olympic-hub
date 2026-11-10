"""Общие фикстуры тестов."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def gogovor_record():
    """Тестовая фикстура из задания.

    Это НЕ публикация каталога: она используется только для проверки
    формата библиографической ссылки.
    """
    return {
        "study_id": "test-gogovor",
        "title_original": "Contemporary Disease Management in Quebec",
        "authors": "Gogovor A., Savoie M., Moride Y., Krelenbaum M., Montague T.",
        "container": "Healthcare Quarterly",
        "year": "2008",
        "url": "https://example.org/article",
    }


@pytest.fixture
def olympic_record():
    return {
        "study_id": "test-olympic",
        "title_original": "Olympic Education and Values in Schools",
        "authors": "Иванов П. С.",
        "year": "2019",
        "abstract_original": "The article examines the Olympic education programme in Russian schools.",
    }


@pytest.fixture
def off_topic_record():
    return {
        "study_id": "test-offtopic",
        "title_original": "Breaking the obesity-cancer link in European schools",
        "abstract_original": "A study of obesity prevention strategies and cancer risk factors.",
        "year": "2021",
    }
