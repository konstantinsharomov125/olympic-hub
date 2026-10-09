import os
import json
import re
import requests

# Файлы базы данных
OUTPUT_PATHS = ['generated/web_data.json', 'web_data.json']

# Карта ISO-кодов стран на русский язык
COUNTRY_MAP = {
    'UA': 'Украина',
    'RU': 'Россия',
    'US': 'США',
    'CN': 'Китай',
    'DE': 'Германия',
    'FR': 'Франция',
    'GB': 'Великобритания',
    'JP': 'Япония',
    'PL': 'Польша',
    'BY': 'Беларусь',
    'KZ': 'Казахстан',
    'IT': 'Италия',
    'ES': 'Испания',
    'CA': 'Канада',
    'AU': 'Австралия',
    'BR': 'Бразилия'
}

# Карта языковых кодов
LANGUAGE_MAP = {
    'uk': 'Украинский',
    'ru': 'Русский',
    'en': 'Английский',
    'de': 'Немецкий',
    'fr': 'Французский',
    'es': 'Испанский',
    'zh': 'Китайский',
    'pl': 'Польский'
}

# 10 Стандартных категорий олимпизма
CATEGORIES = [
    "Олимпийское образование и просвещение",
    "Пропаганда, философия и культурология",
    "История и наследие олимпизма",
    "Этика, честная игра и антидопинг",
    "Политика, геополитика и глобальные вызовы",
    "Психология олимпийского спорта",
    "Менеджмент, маркетинг и экономика Игр",
    "Спортивная медицина, физиология и биомеханика",
    "Подготовка олимпийского резерва и тренировка",
    "Теория и методология олимпийского движения"
]

CATEGORY_KEYWORDS = {
    "Олимпийское образование и просвещение": ["education", "school", "curriculum", "pedagogy", "образование", "школа", "просвещение", "педагогика", "освіта"],
    "Пропаганда, философия и культурология": ["philosophy", "culture", "coubertin", "ideal", "философия", "культура", "ценности", "идеалы", "філософія"],
    "История и наследие олимпизма": ["history", "heritage", "legacy", "ancient", "история", "наследие", "архив", "історія"],
    "Этика, честная игра и антидопинг": ["doping", "anti-doping", "fair play", "ethics", "wada", "допинг", "этика", "честная игра", "допінг"],
    "Политика, геополитика и глобальные вызовы": ["politics", "geopolitics", "boycott", "international relations", "политика", "бойкот", "політика"],
    "Психология олимпийского спорта": ["psychology", "mental", "anxiety", "motivation", "психология", "стресс", "мотивация", "психологія"],
    "Менеджмент, маркетинг и экономика Игр": ["management", "economics", "marketing", "sponsor", "cost", "менеджмент", "экономика", "маркетинг", "економіка"],
    "Спортивная медицина, физиология и биомеханика": ["medicine", "injury", "physiology", "biomechanics", "cardiac", "медицина", "травма", "физиология", "биомеханика"],
    "Подготовка олимпийского резерва и тренировка": ["training", "athlete", "performance", "coaching", "adaptive", "veterans", "тренировка", "подготовка", "резерв", "адаптивный", "ветераны", "тренування", "ветеранів", "адаптивний"],
    "Теория и методология олимпийского движения": ["theory", "methodology", "system", "framework", "теория", "методология", "система", "теорія"]
}

SEARCH_QUERIES = [
    "олимпизм", "олимпийские игры", "олимпийское движение", "олимпийское образование",
    "олимпийский спорт", "антидопинг олимпиада", "история олимпийских игр", "философия олимпизма",
    "Olympic Games", "Olympics sports", "Olympic education", "Olympic movement",
    "Olympic history", "Olympic legacy", "Olympic psychology", "Olympic marketing"
]

def load_existing_data():
    for path in OUTPUT_PATHS:
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list) and len(data) > 0:
                        return data
            except Exception:
                pass
    return []

def save_data(data):
    for path in OUTPUT_PATHS:
        if os.path.dirname(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ В базе данных успешно сохранено {len(data)} исследований.")

def detect_language(title, summary, raw_lang=None):
    """Точное определение языка по коду и символам"""
    text = f"{title} {summary}"
    if re.search(r'[іїєґІЇЄҐ]', text):
        return "Украинский"
    if raw_lang and raw_lang.lower() in LANGUAGE_MAP:
        return LANGUAGE_MAP[raw_lang.lower()]
    if re.search(r'[а-яА-Я]', text):
        return "Русский"
    return "Английский"

def detect_country(country_code, title, summary, language):
    """Точное определение страны по коду ВУЗа/институции"""
    if country_code and country_code.upper() in COUNTRY_MAP:
        return COUNTRY_MAP[country_code.upper()]
    
    text = f"{title} {summary}".lower()
    if language == "Украинский" or "украин" in text or "ukraine" in text or "харків" in text or "київ" in text or "львів" in text:
        return "Украина"
    if language == "Русский" or "росси" in text or "russia" in text or "москв" in text:
        return "Россия"
    
    return "Другие страны"

def classify_text(text):
    text_lower = text.lower()
    scores = {}
    for cat, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[cat] = score
    if scores:
        return max(scores, key=scores.get)
    return "Теория и методология олимпийского движения"

def normalize_doc_type(raw):
    if not raw: return 'Научная статья'
    s = str(raw).lower()
    if 'диссертац' in s or 'dissertation' in s or 'thesis' in s: return 'Диссертация'
    if 'обзор' in s or 'review' in s: return 'Обзорная статья'
    if 'учебн' in s or 'manual' in s or 'textbook' in s: return 'Учебное пособие'
    if 'book' in s or 'монограф' in s: return 'Монография'
    if 'conf' in s or 'материал' in s or 'доклад' in s or 'proceedings' in s: return 'Материалы конференции'
    return 'Научная статья'

def fetch_openalex(query, fetch_limit=50):
    print(f"🌐 [OpenAlex API] Поиск по запросу: '{query}'...")
    url = "https://api.openalex.org/works"
    params = {'search': query, 'per-page': fetch_limit, 'sort': 'publication_year:desc'}
    headers = {'User-Agent': 'OlympicResearchHub/1.0 (mailto:research@olympic-hub.ru)'}
    records = []
    try:
        res = requests.get(url, params=params, headers=headers, timeout=15)
        if res.status_code == 200:
            for item in res.json().get('results', []):
                title = item.get('title', '')
                if not title or len(title) < 5: continue

                # Извлечение авторов и кода страны ВУЗа
                authors_list = []
                country_code = None
                for a in item.get('authorships', []):
                    name = a.get('author', {}).get('display_name', '')
                    if name: authors_list.append(name)
                    if not country_code:
                        for inst in a.get('institutions', []):
                            cc = inst.get('country_code')
                            if cc:
                                country_code = cc
                                break
                
                authors_str = ", ".join(authors_list) if authors_list else "Автор не указан"

                abstract = "Аннотация к исследованию доступна по ссылке на оригинал."
                inv_abstract = item.get('abstract_inverted_index')
                if inv_abstract:
                    try:
                        word_list = []
                        for word, positions in inv_abstract.items():
                            for pos in positions: word_list.append((pos, word))
                        word_list.sort(key=lambda x: x[0])
                        abstract = " ".join([w[1] for w in word_list])
                    except Exception: pass

                year = item.get('publication_year', 2024)
                category = classify_text(f"{title} {abstract}")
                doi = item.get('doi', '')
                url_link = doi if doi else item.get('id', 'https://scholar.google.com')

                lang = detect_language(title, abstract, item.get('language'))
                country = detect_country(country_code, title, abstract, lang)
                doc_type = normalize_doc_type(item.get('type'))

                records.append({
                    "title": title, "title_original": title, "summary": abstract, "abstract": abstract,
                    "authors": authors_str, "year": year, "category": category, "discipline": category,
                    "type": doc_type, "country": country, "language": lang, "url": url_link
                })
    except Exception as e:
        print(f"⚠️ Ошибка OpenAlex: {e}")
    return records

def audit_and_repair_existing_data(existing_data):
    """Автоматическое исправление метаданных в ранее собранной базе"""
    repaired_count = 0
    for item in existing_data:
        title = item.get('title_original') or item.get('title') or ''
        summary = item.get('summary') or item.get('abstract') or ''
        
        new_lang = detect_language(title, summary, None)
        new_country = detect_country(None, title, summary, new_lang)
        
        if item.get('language') != new_lang or (item.get('country') == 'Россия' and new_country == 'Украина'):
            item['language'] = new_lang
            item['country'] = new_country
            repaired_count += 1
            
    if repaired_count > 0:
        print(f"🛠️ Автоматически перепроверено и исправлено ошибок в метаданных: {repaired_count}")

def run_collector(queries=None, limit_per_query=50):
    if not queries:
        queries = SEARCH_QUERIES

    existing_data = load_existing_data()
    audit_and_repair_existing_data(existing_data)
    
    existing_titles = { (item.get('title_original') or item.get('title') or '').lower().strip() for item in existing_data }
    print(f"📦 Исходный объём имеющейся базы данных: {len(existing_data)} исследований.")

    added_count = 0
    for q in queries:
        new_records = fetch_openalex(q, fetch_limit=limit_per_query)
        for record in new_records:
            norm_title = record['title'].lower().strip()
            if norm_title and norm_title not in existing_titles:
                existing_titles.add(norm_title)
                existing_data.insert(0, record)
                added_count += 1

    print(f"✨ Собрано и добавлено новых уникальных публикаций: {added_count}")
    print(f"📈 Текущий общий объём портала: {len(existing_data)} исследований.")
    save_data(existing_data)

if __name__ == "__main__":
    run_collector()