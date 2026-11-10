"""Тесты научной релевантности каталога."""

from olympic_relevance import (
    ACCEPTED,
    REJECTED,
    REVIEW,
    SUBJECT_OLYMPIAD,
    assess_relevance,
    split_by_relevance,
)


def test_clearly_olympic_accepted(olympic_record):
    decision = assess_relevance(olympic_record)
    assert decision.status == ACCEPTED
    assert decision.reason  # объяснение обязательно


def test_olympic_games_history_accepted():
    decision = assess_relevance(
        {"title_original": "Beijing 2008 and 2022: Olympic legacy and urban policy"}
    )
    assert decision.status == ACCEPTED


def test_paralympic_with_olympic_context_accepted():
    decision = assess_relevance(
        {
            "title_original": "Media Visibility of the Paralympic Games in Greece",
            "abstract_original": "The study analyses Paralympic Games coverage 2016-2024.",
        }
    )
    assert decision.status == ACCEPTED


def test_clearly_off_topic_rejected(off_topic_record):
    decision = assess_relevance(off_topic_record)
    assert decision.status == REJECTED
    assert "олимпизм" in decision.reason.lower() or "тематик" in decision.reason.lower()


def test_boxing_without_olympic_context_rejected():
    decision = assess_relevance(
        {"title_original": "PROFESSIONAL BOXING DEVELOPMENT TRENDS IN RUSSIA"}
    )
    assert decision.status == REJECTED


def test_sauna_health_article_rejected():
    decision = assess_relevance(
        {"title_original": "IMPACT OF SAUNA BATHING ON GENERAL HEALTH - THE LATEST REPORTS"}
    )
    assert decision.status == REJECTED


def test_quebec_medical_article_not_accepted_for_olympic_catalog(gogovor_record):
    """Медицинская статья про Квебек не должна попасть в олимпийский каталог.

    Она используется только как тестовая фикстура формата ссылки и не может
    считаться тематически подходящей.
    """
    decision = assess_relevance(gogovor_record)
    assert decision.status != ACCEPTED
    assert decision.status in (REJECTED, REVIEW)


def test_sport_mention_alone_is_not_enough():
    decision = assess_relevance(
        {
            "title_original": "Comparative Analysis of Pole Vault Training Methods",
            "abstract_original": "The article compares sport training methods used by coaches.",
        }
    )
    # Упоминание спорта и тренировки без олимпийской связи — не повод принимать.
    assert decision.status != ACCEPTED
    assert decision.status == REVIEW
    assert decision.reason



def test_ambiguous_record_goes_to_review_not_accepted():
    decision = assess_relevance(
        {
            "title_original": "Sport Event Branding",
            "abstract_original": "The paper discusses branding of sport events in general.",
        }
    )
    assert decision.status == REVIEW


def test_empty_record_needs_review():
    decision = assess_relevance({"title_original": "Олимпизм"})
    assert decision.status == REVIEW


def test_every_decision_has_reason():
    samples = [
        {"title_original": "Olympic Games Tokyo 2020 legacy"},
        {"title_original": "Obesity prevention programme"},
        {"title_original": "Sport and society"},
    ]
    for sample in samples:
        decision = assess_relevance(sample)
        assert decision.reason, f"нет объяснения для {sample}"
        assert decision.status in (ACCEPTED, REJECTED, REVIEW)


def test_split_by_relevance_partitions_records():
    records = [
        {"title_original": "Olympic Education in Schools", "study_id": "a"},
        {"title_original": "Breaking the obesity-cancer link", "study_id": "b"},
        {"title_original": "Sport Event Branding", "study_id": "c"},
    ]
    accepted, rejected, review, subject = split_by_relevance(records)

    total = len(accepted) + len(rejected) + len(review) + len(subject)
    assert total == 3
    assert all(r["relevance_status"] == ACCEPTED for r in accepted)
    assert all(r["relevance_status"] == REJECTED for r in rejected)
    assert all(r["relevance_status"] == REVIEW for r in review)
    assert all(r["relevance_status"] == SUBJECT_OLYMPIAD for r in subject)
    # Исходные записи сохраняются, а не теряются.
    ids = {r["study_id"] for r in accepted + rejected + review + subject}
    assert ids == {"a", "b", "c"}
