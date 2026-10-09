import os
import json
import re
import requests

# Файлы базы данных
OUTPUT_PATHS = ['generated/web_data.json', 'web_data.json']

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

# Ключевые слова для систематизации по направлениям
CATEGORY_KEYWORDS = {
    "Олимпийское образование и просвещение": ["education", "school", "curriculum", "pedagogy", "образование", "школа", "просвещение", "педагогика"],
    "Пропаганда, философия и культурология": ["philosophy", "culture", "coubertin", "ideal", "философия", "культура", "ценности", "идеалы"],
    "История и наследие олимпизма": ["history", "heritage", "legacy", "ancient", "история", "наследие", "архив", "память"],
    "Этика, честная игра и антидопинг": ["doping", "anti-doping", "fair play", "ethics", "wada", "допинг", "этика", "честная игра"],
    "Политика, геополитика и глобальные вызовы": ["politics", "geopolitics", "boycott", "international relations", "политика", "бойкот", "геополитика"],
    "Психология олимпийского спорта": ["psychology", "mental", "anxiety", "motivation", "психология", "стресс", "мотивация", "состояние"],
    "Менеджмент, маркетинг и экономика Игр": ["management", "economics", "marketing", "sponsor", "cost", "менеджмент", "экономика", "маркетинг", "спонсор"],
    "Спортивная медицина, физиология и биомеханика": ["medicine", "injury", "physiology", "biomechanics", "cardiac", "медицина", "травма", "физиология", "биомеханика"],
    "Подготовка олимпийского резерва и тренировка": ["training", "athlete", "performance", "coaching", "тренировка", "подготовка", "резерв", "спортсмен"],
    "Теория и методология олимпийского движения": ["theory", "methodology", "system", "framework", "теория", "методология", "система", "подход"]
}

# Широкий список поисковых ключей для регулярного обновления
SEARCH_QUERIES = [
    "олимпизм", "олимпийские игры", "олимпийское движение", "олимпийское образование",
    "олимпийский спорт", "антидопинг олимпиада", "история олимпийских игр", "философия олимпизма",
    "Olympic Games", "Olympics sports", "Olympic education", "Olympic movement",
    "Olympic history", "Olympic legacy", "Olympic psychology", "Olympic marketing",
    "Olympic doping", "Olympic athletes training", "Olympic management", "Paralympic Games"
]

def load_existing_data():
    """Загружает исходный массив данных из файла web_data.json"""
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
    """Сохраняет полностью обновлённый массив данных"""
    for path in OUTPUT_PATHS:
        if os.path.dirname(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ В базе данных успешно сохранено {len(data)} исследований.")

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

def normalize_language(raw, title=''):
    if re.search(r'[а-яА-Я]', title): return 'Русский'
    if not raw: return 'Английский'
    s = str(raw).lower()
    if 'ru' in s or 'rus' in s or 'рус' in s: return 'Русский'
    if 'de' in s or 'ger' in s or 'нем' in s: return 'Немецкий'
    if 'fr' in s or 'fre' in s or 'фра' in s: return 'Французский'
    if 'es' in s or 'spa' in s or 'исп' in s: return 'Испанский'
    return 'Английский'

def normalize_country(raw, is_ru=False):
    if is_ru: return 'Россия'
    if not raw or raw in ['NR', 'N/A', 'null', 'undefined', 'International']: return 'Другие страны'
    s = str(raw).strip().lower()
    if 'russia' in s or 'росси' in s: return 'Россия'
    if 'usa' in s or 'сша' in s or 'america' in s: return 'США'
    if 'china' in s or 'китай' in s: return 'Китай'
    if 'japan' in s or 'япони' in s: return 'Япония'
    if 'germany' in s or 'герман' in s: return 'Германия'
    if 'france' in s or 'франц' in s: return 'Франция'
    if 'uk' in s or 'england' in s or 'великобрит' in s: return 'Великобритания'
    return 'Другие страны'

def fetch_openalex(query, fetch_limit=100):
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

                authors_list = [a.get('author', {}).get('display_name', '') for a in item.get('authorships', []) if a.get('author', {}).get('display_name')]
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

                is_ru = bool(re.search(r'[а-яА-Я]', title))
                lang = normalize_language(item.get('language'), title)
                country = normalize_country(None, is_ru)
                doc_type = normalize_doc_type(item.get('type'))

                records.append({
                    "title": title, "title_original": title, "summary": abstract, "abstract": abstract,
                    "authors": authors_str, "year": year, "category": category, "discipline": category,
                    "type": doc_type, "country": country, "language": lang, "url": url_link
                })
    except Exception as e:
        print(f"⚠️ Ошибка OpenAlex: {e}")
    return records

def fetch_crossref(query, fetch_limit=100):
    print(f"🌐 [Crossref API] Поиск по запросу: '{query}'...")
    url = "https://api.crossref.org/works"
    params = {'query': query, 'rows': fetch_limit, 'sort': 'published', 'order': 'desc'}
    headers = {'User-Agent': 'OlympicResearchHub/1.0 (mailto:research@olympic-hub.ru)'}
    records = []
    try:
        res = requests.get(url, params=params, headers=headers, timeout=15)
        if res.status_code == 200:
            for item in res.json().get('message', {}).get('items', []):
                title = item.get('title', [''])[0]
                if not title or len(title) < 5: continue

                abstract = item.get('abstract', '')
                abstract = re.sub(r'<[^>]+>', '', abstract).strip()
                if not abstract: abstract = f"Научное исследование по теме олимпизма: '{title}'."

                authors_list = [f"{a.get('given', '')} {a.get('family', '')}".strip() for a in item.get('author', []) if a.get('family')]
                authors_str = ", ".join(authors_list) if authors_list else "Автор не указан"

                year = 2024
                date_parts = item.get('published-print', {}).get('date-parts', []) or item.get('published-online', {}).get('date-parts', [])
                if date_parts and date_parts[0]: year = date_parts[0][0]

                category = classify_text(f"{title} {abstract}")
                doi = item.get('DOI', '')
                url_link = f"https://doi.org/{doi}" if doi else item.get('URL', 'https://scholar.google.com')

                is_ru = bool(re.search(r'[а-яА-Я]', title))
                lang = normalize_language(None, title)
                country = normalize_country(None, is_ru)
                doc_type = normalize_doc_type(item.get('type'))

                records.append({
                    "title": title, "title_original": title, "summary": abstract, "abstract": abstract,
                    "authors": authors_str, "year": year, "category": category, "discipline": category,
                    "type": doc_type, "country": country, "language": lang, "url": url_link
                })
    except Exception as e:
        print(f"⚠️ Ошибка Crossref: {e}")
    return records

def run_collector(queries=None, limit_per_query=100):
    """Бесконечный сбор: сохраняет всю имеющуюся базу и добавляет только новые уникальные исследования."""
    if not queries:
        queries = SEARCH_QUERIES

    existing_data = load_existing_data()
    
    # Реестр названий для исключения повторов
    existing_titles = set()
    for item in existing_data:
        title = (item.get('title_original') or item.get('title') or item.get('article') or '').lower().strip()
        if title:
            existing_titles.add(title)

    print(f"📦 Исходный объём имеющейся базы данных: {len(existing_data)} исследований.")

    added_count = 0
    for q in queries:
        new_records = []
        new_records.extend(fetch_openalex(q, fetch_limit=limit_per_query))
        new_records.extend(fetch_crossref(q, fetch_limit=limit_per_query))

        for record in new_records:
            norm_title = record['title'].lower().strip()
            if norm_title and norm_title not in existing_titles:
                existing_titles.add(norm_title)
                existing_data.insert(0, record)  # Добавляем свежие исследования в начало
                added_count += 1

    print(f"✨ Собрано и добавлено новых уникальных публикаций: {added_count}")
    print(f"📈 Текущий общий объём портала: {len(existing_data)} исследований.")
    save_data(existing_data)

if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    if args:
        run_collector([" ".join(args)], limit_per_query=100)
    else:
        run_collector(SEARCH_QUERIES, limit_per_query=100)