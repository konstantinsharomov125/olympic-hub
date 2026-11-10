"""Проверка научной релевантности записей предмету каталога.

Каталог посвящён олимпизму, Олимпийскому движению и олимпийскому спорту.
Запись попадает в публичную выдачу только при подтверждённой связи, иначе
получает статус ``review`` (нужна ручная проверка) или ``rejected``.

Принципы:
  * одного слова «спорт» недостаточно;
  * случайное упоминание «олимпийский» без контекста не засчитывается;
  * при недостатке доказательств выбирается ``review``, а не ``accepted``;
  * каждое решение сопровождается объяснением.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from olympic_hub_core import clean

ACCEPTED = "accepted"
REJECTED = "rejected"
REVIEW = "review"

PUBLIC_STATUS = ACCEPTED
ALL_STATUSES = (ACCEPTED, REJECTED, REVIEW)

#: Сильные маркеры олимпийской тематики.
STRONG_MARKERS: tuple[tuple[str, str], ...] = (
    (r"олимпизм", "олимпизм"),
    (r"олимпийск\w*\s+(игр|движен|образова|культур|наслед|харти|кодекс|комитет|спорт|подготов|резерв)", "олимпийский контекст"),
    (r"олимпиад", "олимпиада"),
    (r"кубертен", "Кубертен"),
    (r"паралимпи", "паралимпийский спорт"),
    (r"дефлимпи", "дефлимпийский спорт"),
    (r"международн\w*\s+олимпийск\w*\s+комитет", "МОК"),
    (r"\bмок\b", "МОК"),
    (r"\bolympism", "olympism"),
    (r"\bolympic\s+(games?|movement|education|culture|legacy|charter|committee|sport|athlete|training|studies|values?|ideals?|truce|flame|torch|medals?)", "olympic context"),
    (r"\bolympiads?\b", "olympiad"),
    (r"\bcoubertin", "Coubertin"),
    (r"\bparalympic", "paralympic sport"),
    (r"\bdeaflympic", "deaflympic sport"),
    (r"\bioc\b", "IOC"),
    (r"\bwada\b", "WADA / антидопинг"),
    (r"антидопинг", "антидопинг"),
    (r"anti-?doping", "anti-doping"),
    (r"олимпия|олимпиадаси|олимпия\w*", "олимпийская тематика (узб.)"),
    (r"post-?olympic", "постолимпийский период"),
    (r"pre-?olympic", "предолимпийский период"),
    (r"олимпийск\w*\s+игр", "олимпийские игры"),
    (r"игр\w*\s+олимпиад", "игры олимпиады"),
)

#: Названия конкретных Игр сами задают олимпийский контекст.
GAMES_NAMES = re.compile(
    r"\b(?:"
    r"летн\w*|зимн\w*|summer|winter|beijing|tokyo|paris|london|rio|sochi|pyeongchang|"
    r"vancouver|athens|sydney|atlanta|barcelona|seoul|moscow|montreal|munich|mexico|rome|"
    r"melbourne|helsinki|berlin|los\s+angeles|amsterdam|antwerp|stockholm|st\.?\s*louis|"
    r"париж|токио|пекин|сочи|лондон|москв|афин|рио"
    r")\s*(?:-|–|—)?\s*(?:20\d{2}|19\d{2})",
    re.I,
)

#: «Paris Olympics», «Tokyo 2020 Games» — город Игр без явного слова Games.
CITY_OLYMPICS = re.compile(
    r"\b(?:paris|tokyo|beijing|london|rio|sochi|sydney|athens|atlanta|barcelona|seoul|"
    r"moscow|montreal|munich|mexico\s+city|rome|melbourne|helsinki|berlin|amsterdam|"
    r"antwerp|stockholm|los\s+angeles|pyeongchang|vancouver|париж|токио|пекин|сочи|"
    r"лондон|москв|афин|рио)\s+(?:20\d{2}\s+)?(?:olympics?|games)\b",
    re.I,
)

#: Слова, которые сами по себе НЕ доказывают олимпийскую тематику.
WEAK_WORDS = re.compile(
    r"\b(?:спорт\w*|sport\w*|физическ\w+\s+культур\w*|athlet\w*|фитнес\w*)\b",
    re.I,
)

#: Явные признаки посторонней тематики.
OFF_TOPIC_TOPICS: tuple[tuple[str, str], ...] = (
    (r"obes|ожирен", "ожирение и обмен веществ"),
    (r"cancer|онколог", "онкология"),
    (r"sauna|баня|саун", "баня и общее здоровье"),
    (r"boxing|бокс\b", "профессиональный бокс"),
    (r"diabet|диабет", "диабет"),
    (r"dental|стоматолог|зубн", "стоматология"),
    (r"cardiac surgery|кардиохирург", "кардиохирургия"),
    (r"hospice|паллиатив", "паллиативная помощь"),
)

MIN_TITLE_LEN = 15


@dataclass
class RelevanceDecision:
    status: str
    reason: str
    evidence: list[str] = field(default_factory=list)

    @property
    def is_public(self) -> bool:
        return self.status == PUBLIC_STATUS

    def as_dict(self) -> dict[str, Any]:
        return {"status": self.status, "reason": self.reason, "evidence": self.evidence}


def assess_relevance(record: Mapping[str, Any]) -> RelevanceDecision:
    """Определяет статус релевантности одной записи."""
    title = clean(record.get("title_original") or record.get("title"))
    abstract = clean(
        record.get("abstract_original")
        or record.get("summary")
        or record.get("summary_original")
        or record.get("abstract")
    )
    keywords = clean(record.get("keywords"))
    container = clean(record.get("container") or record.get("source"))

    title_l = title.lower()
    abstract_l = abstract.lower()
    combined = " ".join([title_l, abstract_l, keywords.lower(), container.lower()])

    # 1. Совсем пустая запись — решать не по чему.
    if len(title) < 3 and len(abstract) < 20:
        return RelevanceDecision(REVIEW, "Недостаточно данных: нет названия и аннотации")

    # 2. Сильные маркеры в заголовке.
    title_evidence: list[str] = []
    for pattern, label in STRONG_MARKERS:
        if re.search(pattern, title_l, flags=re.I):
            title_evidence.append(label)

    if GAMES_NAMES.search(title):
        title_evidence.append("название конкретных Игр")
    if CITY_OLYMPICS.search(title):
        title_evidence.append("город и Игры в названии")

    # 3. Сильные маркеры в аннотации и ключевых словах.
    body_evidence: list[str] = []
    body_text = abstract_l + " " + keywords.lower()
    for pattern, label in STRONG_MARKERS:
        if label not in title_evidence and re.search(pattern, body_text, flags=re.I):
            body_evidence.append(label)

    if (title_evidence or body_evidence) and len(title) >= MIN_TITLE_LEN:
        evidence = sorted(set(title_evidence + body_evidence))
        reason = "Подтверждена связь с олимпийской тематикой: " + ", ".join(evidence[:4])
        return RelevanceDecision(ACCEPTED, reason, evidence)

    # Маркер найден в аннотации или ключевых словах — этого достаточно.
    if body_evidence and len(abstract) >= 40:
        evidence = sorted(set(body_evidence))
        reason = "Связь с олимпийской тематикой подтверждена аннотацией: " + ", ".join(evidence[:4])
        return RelevanceDecision(ACCEPTED, reason, evidence)

    # 4. Маркер есть, но заголовок слишком короткий — нужна проверка.
    if title_evidence or body_evidence:
        return RelevanceDecision(
            REVIEW,
            "Олимпийский маркер найден, но название слишком короткое для уверенного решения",
            sorted(set(title_evidence + body_evidence)),
        )

    # 5. Только общее упоминание олимпийской тематики.
    if re.search(r"олимпийск|\bolympic\b", combined):
        return RelevanceDecision(
            REVIEW,
            "Найдено лишь общее упоминание олимпийской тематики без содержательного контекста",
            ["общее упоминание"],
        )

    # 6. Посторонняя тематика без олимпийских маркеров.
    off_topic = [
        label for pattern, label in OFF_TOPIC_TOPICS if re.search(pattern, combined, flags=re.I)
    ]
    if off_topic:
        return RelevanceDecision(
            REJECTED,
            "Тематика не относится к олимпизму: " + ", ".join(sorted(set(off_topic))),
            sorted(set(off_topic)),
        )

    # 7. Упоминается спорт без олимпийской связи.
    if WEAK_WORDS.search(combined):
        return RelevanceDecision(
            REVIEW,
            "Упоминается спорт, но связь с олимпийским движением не подтверждена",
            ["только упоминание спорта"],
        )

    # 8. Ничего не найдено.
    if len(abstract) >= 60:
        return RelevanceDecision(
            REJECTED, "В названии и аннотации нет признаков олимпийской тематики"
        )

    return RelevanceDecision(REVIEW, "Недостаточно текста для решения о релевантности")


def split_by_relevance(
    records: Iterable[Mapping[str, Any]],
) -> tuple[list[dict], list[dict], list[dict]]:
    """Делит записи на accepted / rejected / review, сохраняя объяснения."""
    accepted: list[dict] = []
    rejected: list[dict] = []
    review: list[dict] = []
    buckets = {ACCEPTED: accepted, REJECTED: rejected, REVIEW: review}

    for record in records:
        decision = assess_relevance(record)
        enriched = dict(record)
        enriched["relevance_status"] = decision.status
        enriched["relevance_reason"] = decision.reason
        enriched["relevance_evidence"] = decision.evidence
        buckets[decision.status].append(enriched)

    return accepted, rejected, review

