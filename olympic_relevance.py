"""Проверка научной релевантности записей предмету каталога.

Каталог посвящён олимпизму, Олимпийскому движению и олимпийскому спорту.
Запись попадает в публичную выдачу только при подтверждённой связи, иначе
получает статус ``review`` (нужна ручная проверка) или ``rejected``.

Принципы (после аудита публикаций):

  * имена авторов НЕ являются доказательством тематики («Олимпиада Иванова»);
  * слово «движение» без олимпийского контекста — не олимпийское движение;
  * школьные и предметные олимпиады — отдельный статус ``subject_olympiad``;
  * случайное упоминание Олимпийских игр (инфраструктура, геохимия,
    охрана труда) не принимается без подтверждения темы;
  * одиночное совпадение подстроки «олимп» ничего не доказывает;
  * при недостатке доказательств выбирается ``review``, а не ``accepted``;
  * у каждого принятого решения есть ``relevance_evidence`` — понятное
    объяснение, какие именно подтверждения найдены и где.

Подтверждением считаются только содержательные маркеры: олимпизм, Игры,
МОК, Кубертен, олимпийское образование/философия/движение/наследие,
олимпийский спорт с явным признаком олимпийской квалификации спортсмена.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from olympic_hub_core import clean

ACCEPTED = "accepted"
REJECTED = "rejected"
REVIEW = "review"
#: Школьные и предметные олимпиады, студенческие конкурсы, интеллектуальные
#: состязания. Тематически близки по слову, но не относятся к Олимпийским играм.
SUBJECT_OLYMPIAD = "subject_olympiad"

PUBLIC_STATUS = ACCEPTED
ALL_STATUSES = (ACCEPTED, REJECTED, REVIEW, SUBJECT_OLYMPIAD)

#: Минимальная длина названия для уверенного решения.
MIN_TITLE_LEN = 15

# --------------------------------------------------------------------------
# Тематические направления
# --------------------------------------------------------------------------

TOPIC_CORE_IDEALS = "олимпизм и олимпийские ценности"
TOPIC_GAMES = "Олимпийские игры"
TOPIC_MOVEMENT = "Олимпийское движение и МОК"
TOPIC_EDUCATION = "олимпийское образование"
TOPIC_PHILOSOPHY = "олимпийская философия и история"
TOPIC_LEGACY = "олимпийское наследие"
TOPIC_PARALYMPIC = "паралимпийское движение"
TOPIC_ANTIDOPING = "антидопинговая политика и WADA"
TOPIC_SCIENCE = "спортивная наука об олимпийском спорте"

#: Направления, которые сами по себе доказывают принадлежность каталогу.
CORE_TOPICS: frozenset[str] = frozenset(
    {
        TOPIC_CORE_IDEALS,
        TOPIC_GAMES,
        TOPIC_MOVEMENT,
        TOPIC_EDUCATION,
        TOPIC_PHILOSOPHY,
        TOPIC_LEGACY,
        TOPIC_PARALYMPIC,
        TOPIC_ANTIDOPING,
    }
)

#: Направление, которое требует дополнительного подтверждения (спорт).
CONDITIONAL_TOPICS: frozenset[str] = frozenset({TOPIC_SCIENCE})

# --------------------------------------------------------------------------
# Шаблоны
# --------------------------------------------------------------------------

#: (регулярное выражение, направление, подпись подтверждения)
#:
#: Границы слов записываются явно ``(?<![а-яёa-z])`` / ``(?![а-яёa-z])``:
#: встроенный ``\b`` в Python даёт разные результаты для кириллицы и
#: латиницы в смешанном тексте, а ``\w`` захватывает кириллицу.
_A = r"(?<![а-яёa-z])"
_Z = r"(?![а-яёa-z])"

TITLE_MARKERS: tuple[tuple[str, str, str], ...] = (
    # --- Олимпизм и ценности ---
    (r"олимпизм", TOPIC_CORE_IDEALS, "олимпизм"),
    (r"олимпийск\w*\s+(?:ценност|идеал|философ|воспитан|традиц|гуманизм|дух)", TOPIC_CORE_IDEALS,
     "олимпийские ценности"),
    # --- Олимпийское образование ---
    (r"олимпийск\w*\s+(?:образова|просвещен|педагог|обучен|знани)", TOPIC_EDUCATION,
     "олимпийское образование"),
    # --- Движение и МОК ---
    (r"олимпийск\w*\s+(?:движен|комитет|харти|конгресс|солидарн|академ|конференц)",
     TOPIC_MOVEMENT, "Олимпийское движение"),
    # --- Наследие, экономика, менеджмент Игр ---
    (r"олимпийск\w*\s+(?:наслед|объект|стадион|деревн|туризм|экономик|менеджмент|маркетинг|"
     r"инфраструктур|заявк|строительств)", TOPIC_LEGACY, "олимпийское наследие"),
    # --- Соревнования, спортсмены, виды спорта ---
    (r"олимпийск\w*\s+(?:игр|медал|чемпион|участник|спортсмен|сборн|вид\w*\s+спорт|рекорд|"
     r"соревнован|программ|дисциплин|турнир|отбор|квалификац|подготовк|резерв|бадминтон|"
     r"плаван|легк\w*\s+атлетик|гимнастик|фехтован|бокс|борьб|гребл|парусн|лыжн|биатлон|"
     r"фигурн|конькобежн|хокке|сёрф|серф|скейт|каратэ|карате|дзюдо|тхэквондо|стрельб)",
     TOPIC_GAMES, "олимпийские соревнования"),
    # --- История и символика ---
    (r"олимпийск\w*\s+(?:истор|археолог|символ|эмблем|огн|факел|церемони|девиз|гимн)",
     TOPIC_PHILOSOPHY, "олимпийская символика и история"),
    (r"игр\w*\s+олимпиад", TOPIC_GAMES, "Игры Олимпиад"),
    (r"\bолимпиад\w*", TOPIC_GAMES, "Олимпиада как соревнование"),
    (r"кубертен", TOPIC_PHILOSOPHY, "Пьер де Кубертен"),
    (r"паралимпи", TOPIC_PARALYMPIC, "паралимпийский спорт"),
    (r"дефлимпи", TOPIC_PARALYMPIC, "сурдлимпийское движение"),
    (r"(?<![а-яёa-z])мок(?![а-яёa-z])|международн\w*\s+олимпийск\w*\s+комитет",
     TOPIC_MOVEMENT, "МОК"),
    (r"антидопинг|\bвада\b|world\s+anti-?doping", TOPIC_ANTIDOPING, "антидопинговая политика"),
    # --- Английские маркеры ---
    (r"\bolympism", TOPIC_CORE_IDEALS, "olympism"),
    (r"\bolympic\s+(?:games?|events?|olympiads?|winter|summer)", TOPIC_GAMES, "Olympic Games"),
    (r"\bolympic\s+(?:movement|committee|charter|congress|solidarity|academy|truce|family)",
     TOPIC_MOVEMENT, "Olympic movement"),
    (r"\bolympic\s+(?:education|pedagog\w*|values?|ideals?|philosoph\w*|cultures?|tradition\w*|"
     r"spirit|principles?)", TOPIC_EDUCATION, "Olympic education and values"),
    (r"\bolympic\s+(?:legacy|heritage|infrastructur\w*|venues?|stadiums?|village|tourism|"
     r"econom\w*|manag\w*|marketing|bidding|hosting|candidac\w*|facilit\w*)",
     TOPIC_LEGACY, "Olympic legacy"),
    # --- Олимпийский спорт: широкий набор видов и ролей ---
    (r"\bolympic\s+(?:athletes?|champions?|medal\w*|sports?|disciplines?|qualification|"
     r"selection|records?|torch|flame|symbols?|ceremon\w*|history|histor\w*|studies|"
     r"programme?|competitions?|tournament|swimming|badminton|gymnastics|fencing|boxing|"
     r"wrestling|rowing|sailing|skiing|biathlon|hockey|judo|taekwondo|shooting|"
     r"weightlifting|athletics|cycling|marathon|diving|surfing|skateboarding|"
     r"basketball|football|volleyball|handball|triathlon|equestrian)", TOPIC_GAMES, "Olympic sport"),
    (r"\bolympic\b(?!\s+(?:airways|park|council|national|village\s+hotel|"
     r"paint|coffee|steel|museum\s+of\s+art|dances?|symphon|concerto|sonata|"
     r"overture|suite|ballet|opera))", TOPIC_GAMES, "Olympic Games"),
    (r"\bpre-?olympic\w*|\bpost-?olympic\w*", TOPIC_GAMES, "олимпийский цикл"),
    (r"\bparalympic\w*", TOPIC_PARALYMPIC, "paralympic sport"),
    (r"\bcoubertin\b", TOPIC_PHILOSOPHY, "Пьер де Кубертен"),
    (r"\bioc\b", TOPIC_MOVEMENT, "МОК"),
    (r"\bwada\b", TOPIC_ANTIDOPING, "WADA"),
    (r"\banti-?doping\b|\bdoping\b", TOPIC_ANTIDOPING, "anti-doping"),
)


#: Для аннотации и ключевых слов действуют те же маркеры.
BODY_MARKERS = TITLE_MARKERS

#: Явные названия конкретных Игр (город или сезон + год).
GAMES_NAMES = re.compile(
    r"\b(?:"
    r"летн\w*|зимн\w*|summer|winter|"
    r"beijing|tokyo|paris|london|rio|sochi|pyeongchang|vancouver|athens|sydney|atlanta|"
    r"barcelona|seoul|moscow|montreal|munich|mexico|rome|melbourne|helsinki|berlin|"
    r"los\s+angeles|amsterdam|antwerp|stockholm|st\.?\s*louis|brisbane|milan|cortina|"
    r"париж|токио|пекин|сочи|лондон|москв|афин|рио|милан"
    r")\s*(?:-|–|—)?\s*(?:20\d{2}|19\d{2})",
    re.I,
)

#: «Paris Olympics», «Tokyo 2020 Games» — город Игр без слова Games.
CITY_OLYMPICS = re.compile(
    r"\b(?:paris|tokyo|beijing|london|rio|sochi|sydney|athens|atlanta|barcelona|seoul|"
    r"moscow|montreal|munich|mexico\s+city|rome|melbourne|helsinki|berlin|amsterdam|"
    r"antwerp|stockholm|los\s+angeles|pyeongchang|vancouver|париж|токио|пекин|сочи|"
    r"лондон|москв|афин|рио)\s+(?:20\d{2}\s+)?(?:olympics?|games|олимпиад\w*|игр\w*)\b",
    re.I,
)

#: Признаки школьной / предметной / студенческой олимпиады.
SUBJECT_OLYMPIAD_RE = re.compile(
    # «Олимпиада по физике», «олимпиада по математике для школьников»
    r"олимпиад\w*\s+(?:по|для)\s+(?:физик|матем|хим|биолог|информат|географ|"
    r"астроном|экономик|литератур|русск|англ|истор|обществ|эколог|школьник|студент|учащ|"
    r"предмет)"
    r"|школьн\w*\s+олимпиад"
    r"|предметн\w*\s+олимпиад"
    r"|олимпиад\w*\s+(?:школьник|учащ|студент|дошкольн)"
    r"|(?:всероссийск\w*|региональн\w*|муниципальн\w*|городск\w*|областн\w*)\s+"
    r"олимпиад\w*\s+(?:школьник|учащ|студент|по\s+)"
    r"|(?:математик|физик|хими|биолог|информатик|географ|астроном|экономик|литературн)\w*\s+олимпиад"
    # Английские предметные олимпиады: «Physics Olympics», «A Spelling Olympics»
    r"|\b(?:physics|chemistry|biology|mathematics|math|science|spelling|reading|"
    r"geography|astronomy|robotics|geology|history|debate|music)\s+olympics?\b"
    r"|subject\s+olympiad|school\s+olympiad|olympiad\s+in\s+(?:mathematics|physics|chemistry|biology|informatics)"
    r"|high\s+school\s+science\s+students"
    r"|competitions?\s+for\s+(?:secondary|high\s+school|school)\s+\w+\s+students"
    r"|\bolympics?\s+of\s+the\s+mind\b"
    r"|intellectual\s+(?:competition|olympiad|games?)"
    # «X Olympics» где X — учебный предмет: «Metric Olympics», «Chemistry Olympics»
    r"|\b(?:chemistry|biology|physics|math|metric)\s+olympics?\b",
    re.I,
)


#: «Олимпиада Иванова» — имя, а не тематика.
_OLYMPIADA_NAME = re.compile(r"олимпиад\w*\s+[А-ЯЁ][а-яё]+|\bOlympiada\s+[A-Z][a-z]+")

#: Употребления слова «олимпийский», не имеющие отношения к Играм:
#: музыкальные произведения, театры, отели, бренды, косметика.
NON_OLYMPIC_USAGE_RE = re.compile(
    r"\bolympic\s+(?:dances?|symphon\w*|concerto|sonata|overture|suite|ballet|opera|"
    r"theatre|theater|hotel|airways|cruis\w*|paints?|coffee|steel|brewery|resort|"
    r"casino|shopping|cinema|games?\s+console|nintendo|videogame)"
    r"|олимпийск\w*\s+(?:гостиниц|театр|авиалини|круиз|пивовар)"
    r"|\bolympia\s+(?:dances?|paints?|theatre|hall|cafe|hotel)",
    re.I,
)

#: Имя автора «Олимпиада» ловим в поле авторов.
_AUTHOR_NAME_OLYMPIADA = re.compile(r"\bолимпиад\w+\b", re.I)

#: Слова, которые тянет за собой ложную тематику, если стоят без контекста.
FALSE_FRIEND_RE = re.compile(r"\bолимп\w*", re.I)

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

#: Общие слова, которые НЕ доказывают олимпийскую тематику.
WEAK_WORDS = re.compile(
    r"\b(?:спорт\w*|sport\w*|физическ\w+\s+культур\w*|athlet\w*|фитнес\w*|"
    r"движение|movement|олимпийск\w*|olympic\w*)\b",
    re.I,
)

#: Признак «элитного» спорта — ключ к пункту о спортивной науке.
OLYMPIC_QUALIFIER_RE = re.compile(
    r"\b(?:elite|international|world[- ]class|national\s+team|olympic[- ](?:level|standard|"
    r"qualification|eligible|athletes?|squad)|high[- ]performance|professional\s+athlete\w*|"
    r"элитн\w*|высококвалифицированн\w*|сборн\w*\s+команд\w*|олимпийск\w*\s+(?:резерв|уровн|"
    r"стандарт|квалификац|отбор))",
    re.I,
)

#: Явные признаки посторонней научной дисциплины.
FOREIGN_DISCIPLINE_RE = re.compile(
    r"\b(?:sodium|sulfate|geochem\w*|hydrogeol\w*|chromatograph\w*|spectroscop\w*|crystall\w*|"
    r"aqueous\s+solution|solubilit\w*|thermodynamic\w*|buffer\s+solution|pH[- ]value|"
    r"растворим\w*|осадок|эвтектик\w*|фазов\w*\s+равновеси\w*|кристаллизац\w*|"
    r"калориметр\w*|растворител\w*|титрован\w*|хроматограф\w*|taphonom\w*|"
    r"дешифровк\w*|нумизматик\w*)\b",
    re.I,
)

#: Слова «инфраструктурного» контекста — ОИ упомянуты, но тема другая.
INCIDENTAL_CONTEXT_RE = re.compile(
    r"\b(?:dredg\w*|eutrophicat\w*|silting|waste\s+management|landfill|occupational|"
    r"heat\s+illness|workplace|workers?\b|wearables?|"
    r"дреджинг\w*|эвтрофикац\w*|загрязнен\w*|свалк\w*|отход\w*|охрана\s+труда|"
    r"трудоохранн\w*)\b",
    re.I,
)

#: Признаки точной научной дисциплины в названии. Если название целиком
#: про химию/геохимию, а олимпийские слова есть только в аннотации,
#: источник, вероятнее всего, склеил разные записи.
DOMAIN_TITLE_RE = re.compile(
    r"(?:фазов\w+\s+равновеси|солев\w+\s+систем|sodium|sulfate|carbonate|"
    r"geochem\w*|biogeochem\w*|sediment|estuary|chromatograph\w*|spectroscop\w*|"
    r"crystall\w*|thermodynamic\w*|synthes\w*|nanoparticle|polymer|"
    r"фазовая|литий|хлорид|сульфат|карбонат|осадк|раствор)",
    re.I,
)


@dataclass
class RelevanceDecision:
    status: str
    reason: str
    evidence: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)

    @property
    def is_public(self) -> bool:
        return self.status == PUBLIC_STATUS

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "reason": self.reason,
            "evidence": self.evidence,
            "topics": self.topics,
        }


def _find_markers(text: str, patterns) -> list[tuple[str, str]]:
    """Возвращает найденные пары (направление, подпись) без повторов."""
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    for pattern, topic, label in patterns:
        if label in seen:
            continue
        if re.search(pattern, text, flags=re.I):
            found.append((topic, label))
            seen.add(label)
    return found


def _format_evidence(where: str, labels: list[str]) -> str:
    return f"{where}: " + ", ".join(labels)


def _snippet(text: str, limit: int = 70) -> str:
    match = re.search(r"олимп\w*", text, flags=re.I)
    if not match:
        return text[:limit].strip()
    start = max(0, match.start() - 25)
    return text[start : match.end() + 25].strip()[:limit]


def assess_relevance(record: Mapping[str, Any]) -> RelevanceDecision:
    """Определяет статус релевантности одной записи.

    Порядок проверок — часть приоритетов решения; он зафиксирован
    комментариями и покрыт регрессионными тестами.
    """
    title = clean(record.get("title_original") or record.get("title"))
    abstract = clean(
        record.get("abstract_original")
        or record.get("summary")
        or record.get("summary_original")
        or record.get("abstract")
    )
    keywords = clean(record.get("keywords"))
    container = clean(record.get("container") or record.get("source"))
    authors = clean(record.get("authors") or record.get("author"))

    title_l = title.lower()
    abstract_l = abstract.lower()
    keywords_l = keywords.lower()
    container_l = container.lower()
    body_text = " ".join([abstract_l, keywords_l])
    combined = " ".join([title_l, abstract_l, keywords_l, container_l])

    # 0. Пустая запись — решать не по чему.
    if len(title) < 3 and len(abstract) < 20:
        return RelevanceDecision(REVIEW, "Недостаточно данных: нет названия и аннотации", [])

    # 1. Имя «Олимпиада» в авторе — не доказательство тематики.
    author_is_olympiada = bool(_AUTHOR_NAME_OLYMPIADA.search(authors))
    if author_is_olympiada:
        authors = ""

    # 2. Олимпийский контекст: направления из названия и текста.
    title_hits = _find_markers(title_l, TITLE_MARKERS)
    body_hits = _find_markers(body_text, BODY_MARKERS)

    # Неолимпийские употребления («Olympic Dances», отель, авиалинии)
    # дискредитируют все совпадения слова «олимпийский».
    if NON_OLYMPIC_USAGE_RE.search(title_l) or NON_OLYMPIC_USAGE_RE.search(abstract_l):
        title_hits = [
            hit for hit in title_hits if hit[1] not in {"Olympic Games", "Olympic sport"}
        ]
        body_hits = [
            hit for hit in body_hits if hit[1] not in {"Olympic Games", "Olympic sport"}
        ]

    if GAMES_NAMES.search(title):
        title_hits.append((TOPIC_GAMES, "названия конкретных Игр"))
    if CITY_OLYMPICS.search(title):
        title_hits.append((TOPIC_GAMES, "город и Игры в названии"))

    title_topics = {topic for topic, _ in title_hits}
    body_topics = {topic for topic, _ in body_hits}
    topics = sorted(title_topics | body_topics)

    core_in_title = title_topics & CORE_TOPICS
    core_in_body = body_topics & CORE_TOPICS

    author_note = ["имена авторов доказательством не считаются"] if author_is_olympiada else []

    # 3. Школьные и предметные олимпиады — отдельный статус, не каталог Игр.
    # Слово «олимпиада» само по себе не делает запись олимпийской: если в
    # названии/аннотации есть предметная олимпиада, а явных терминов об
    # Олимпийских играх нет, запись не публикуется.
    subject_context = bool(
        SUBJECT_OLYMPIAD_RE.search(title_l) or SUBJECT_OLYMPIAD_RE.search(abstract_l)
    )
    games_context = bool(
        title_topics & (CORE_TOPICS - {TOPIC_GAMES})
        or body_topics & (CORE_TOPICS - {TOPIC_GAMES})
        or GAMES_NAMES.search(title)
        or CITY_OLYMPICS.search(title)
    )
    if subject_context and not games_context:
        return RelevanceDecision(
            SUBJECT_OLYMPIAD,
            "Речь идёт о школьной или предметной олимпиаде, а не об Олимпийских играх",
            ["школьная/предметная олимпиада: " + _snippet(title_l or abstract_l)],
            ["предметная олимпиада"],
        )

    # 4. Сильный маркер в названии при достаточной длине названия.
    if core_in_title and len(title) >= MIN_TITLE_LEN:
        labels = sorted({label for _, label in title_hits})
        evidence = [_format_evidence("название", labels)]
        if body_hits:
            evidence.append(
                _format_evidence(
                    "аннотация/ключевые слова",
                    sorted({label for _, label in body_hits})[:3],
                )
            )
        evidence += author_note
        return RelevanceDecision(
            ACCEPTED,
            "Связь с олимпийской тематикой подтверждена названием: " + ", ".join(labels[:4]),
            evidence,
            topics,
        )

    # 4б. Название без олимпийских маркеров, а в тексте — служебный контекст
    # (охрана труда, инфраструктура, геохимия). Олимпийские Игры лишь
    # упоминаются как пример, поэтому запись в каталог не идёт.
    incidental = bool(INCIDENTAL_CONTEXT_RE.search(combined)) or bool(
        FOREIGN_DISCIPLINE_RE.search(combined)
    )
    if incidental and not core_in_title:
        return RelevanceDecision(
            REJECTED,
            "Олимпийские игры упомянуты только как внешний контекст (инфраструктура, "
            "среда, охрана труда); сама публикация к олимпизму не относится",
            ["упоминание Игр как сопутствующего контекста"],
            topics,
        )

    # 5. Сильный маркер в аннотации или ключевых словах.
    if core_in_body:
        labels = sorted({label for _, label in body_hits})
        # Название про другую дисциплину (химия, геохимия), а олимпийские
        # слова только в аннотации — вероятна склейка разных записей.
        if DOMAIN_TITLE_RE.search(title_l) and not core_in_title:
            return RelevanceDecision(
                REVIEW,
                "Название относится к другой научной дисциплине, а олимпийские "
                "термины найдены только в аннотации: требуется ручная проверка",
                ["расхождение темы названия и аннотации: " + _snippet(title_l)],
                topics,
            )
        if len(abstract) >= 40 or keywords_l:
            where = "аннотация" if len(abstract) >= 40 else "ключевые слова"
            evidence = [
                _format_evidence(where, labels[:4]),
                "название: " + title[:80],
            ]
            evidence += author_note
            return RelevanceDecision(
                ACCEPTED,
                "Связь с олимпийской тематикой подтверждена аннотацией: " + ", ".join(labels[:4]),
                evidence,
                topics,
            )
        # Аннотации нет — контекст проверить нельзя.
        return RelevanceDecision(
            REVIEW,
            "Олимпийский термин найден, но аннотация отсутствует: связь не подтверждена",
            [_format_evidence("ключевые слова", labels[:4])] + author_note,
            topics,
        )

    # 6. Спортивная наука: нужна явная олимпийская квалификация спортсменов.
    if TOPIC_SCIENCE in topics and OLYMPIC_QUALIFIER_RE.search(combined):
        return RelevanceDecision(
            ACCEPTED,
            "Спортивная наука об атлетах олимпийского уровня подтверждена аннотацией",
            ["олимпийская квалификация спортсменов: " + _snippet(combined)],
            [TOPIC_SCIENCE],
        )

    # 8. Общее упоминание олимпийской тематики без содержательного контекста.
    if FALSE_FRIEND_RE.search(title_l + " " + body_text):
        evidence = ["слово «олимп…» без олимпийского термина: " + _snippet(title_l or abstract_l)]
        evidence += author_note
        return RelevanceDecision(
            REVIEW,
            "Найдено лишь общее упоминание олимпийской тематики без содержательного контекста",
            evidence,
            topics,
        )

    # 9. Явно посторонняя тематика.
    off_topic = sorted(
        {label for pattern, label in OFF_TOPIC_TOPICS if re.search(pattern, combined, flags=re.I)}
    )
    if off_topic:
        return RelevanceDecision(
            REJECTED,
            "Тематика не относится к олимпизму: " + ", ".join(off_topic),
            off_topic,
        )

    # 10. Упоминается спорт или «движение» без олимпийской связи.
    if WEAK_WORDS.search(combined):
        return RelevanceDecision(
            REVIEW,
            "Упоминается спорт или «движение», но связь с олимпийским движением не подтверждена",
            ["общее упоминание спорта/движения"],
        )

    # 11. Ничего не найдено.
    if len(abstract) >= 60:
        return RelevanceDecision(REJECTED, "В названии и аннотации нет признаков олимпийской тематики")

    return RelevanceDecision(
        REVIEW,
        "Недостаточно текста для уверенного решения о релевантности: нужна ручная проверка",
    )


def split_by_relevance(
    records: Iterable[Mapping[str, Any]],
) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    """Делит записи на accepted / rejected / review / subject_olympiad.

    Возвращает кортеж в порядке: accepted, rejected, review, subject_olympiad.
    Объяснения решений сохраняются в каждой записи.
    """
    accepted: list[dict] = []
    rejected: list[dict] = []
    review: list[dict] = []
    subject: list[dict] = []
    buckets = {
        ACCEPTED: accepted,
        REJECTED: rejected,
        REVIEW: review,
        SUBJECT_OLYMPIAD: subject,
    }

    for record in records:
        decision = assess_relevance(record)
        enriched = dict(record)
        enriched["relevance_status"] = decision.status
        enriched["relevance_reason"] = decision.reason
        enriched["relevance_evidence"] = decision.evidence
        enriched["relevance_topics"] = decision.topics
        buckets[decision.status].append(enriched)

    return accepted, rejected, review, subject




