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

# Ключевые слова для автоматической классификации по категориям
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

def load_existing_data():
    """Загрузка существующей базы данных"""
    for path in OUTPUT_PATHS:
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data if isinstance(data, list) else []
            except Exception:
                pass
    return []

def save_data(data):
    """Сохранение обновленной базы данных"""
    for path in OUTPUT_PATHS:
        os.makedirs(os.path.dirname(path), exist_ok=True) if os.path.dirname(path) else None
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ Успешно сохранено {len(data)} записей в файл базы данных.")

def classify_text(text):
    """Автоматическое определение категории статьи по ключевым словам"""
    text_lower = text.lower()
    scores = {}
    for cat, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[cat] = score
    
    if scores:
        return max(scores, key=scores.get)
    return "Теория и методология олимпийского движения"

def normalize_country_from_text(location_str):
    """Определение страны исследования"""
    if not location_str:
        return "Другие страны"
    loc = location_str.lower()
    if "russia" in loc or "росси" in loc or "moscow" in loc or "казань" in loc:
        return "Россия"
    if "usa" in loc or "united states" in loc or "сша" in loc:
        return "США"
    if "china" in loc or "китай" in loc:
        return "Китай"
    if "france" in loc or "франц" in loc:
        return "Франция"
    if "germany" in loc or "герман" in loc:
        return "Германия"
    return "Другие страны"

def fetch_openalex(query, limit=25):
    """Сбор с OpenAlex (включает КиберЛенинку, ВУЗовские репозитории и статьи eLibrary с DOI)"""
    print(f"🔍 [OpenAlex API] Запрос исследований по теме: '{query}'...")
    url = "https://api.openalex.org/works"
    params = {
        'search': query,
        'per-page': limit,
        'sort': 'publication_year:desc'
    }
    headers = {'User-Agent': 'OlympicResearchHub/1.0 (mailto:research@olympic-hub.ru)'}
    
    records = []
    try:
        response = requests.get(url, params=params, headers=headers, timeout=12)
        if response.status_code == 200:
            results = response.json().get('results', [])
            for item in results:
                title = item.get('title', '')
                if not title:
                    continue

                # Извлечение авторов
                authors_list = []
                for auth in item.get('authorships', []):
                    name = auth.get('author', {}).get('display_name', '')
                    if name:
                        authors_list.append(name)
                authors_str = ", ".join(authors_list) if authors_list else "Автор не указан"

                # Извлечение абстракта (OpenAlex хранит абстракт в виде инвертированного индекса)
                abstract = "Аннотация к исследованию доступна в оригинале статьи."
                inv_abstract = item.get('abstract_inverted_index')
                if inv_abstract:
                    try:
                        word_list = []
                        for word, positions in inv_abstract.items():
                            for pos in positions:
                                word_list.append((pos, word))
                        word_list.sort(key=lambda x: x[0])
                        abstract = " ".join([w[1] for w in word_list])
                    except Exception:
                        pass

                year = item.get('publication_year', 2024)
                category = classify_text(f"{title} {abstract}")
                doi = item.get('doi', '')
                url_link = doi if doi else item.get('id', 'https://scholar.google.com')

                # Определение языка
                lang = item.get('language', '')
                language_str = "Русский" if lang == 'ru' or re.search(r'[а-яА-Я]', title) else "Английский"
                country_str = "Россия" if language_str == "Русский" else "Другие страны"

                records.append({
                    "title": title,
                    "title_original": title,
                    "summary": abstract,
                    "abstract": abstract,
                    "authors": authors_str,
                    "year": year,
                    "category": category,
                    "discipline": category,
                    "type": "Научная статья",
                    "country": country_str,
                    "language": language_str,
                    "url": url_link
                })
    except Exception as e:
        print(f"⚠️ Ошибка запроса к OpenAlex: {e}")
    
    return records

def fetch_crossref(query, limit=20):
    """Сбор исследований с платформы Crossref API"""
    print(f"🔍 [Crossref API] Запрос исследований по теме: '{query}'...")
    url = "https://api.crossref.org/works"
    params = {
        'query': query,
        'rows': limit,
        'sort': 'published',
        'order': 'desc'
    }
    headers = {'User-Agent': 'OlympicResearchHub/1.0 (mailto:research@olympic-hub.ru)'}
    
    records = []
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        if response.status_code == 200:
            items = response.json().get('message', {}).get('items', [])
            for item in items:
                title = item.get('title', [''])[0]
                if not title:
                    continue
                
                abstract = item.get('abstract', '')
                abstract = re.sub(r'<[^>]+>', '', abstract).strip()
                if not abstract:
                    abstract = f"Аннотация к научному исследованию: '{title}'."

                authors_list = []
                for a in item.get('author', []):
                    name = f"{a.get('given', '')} {a.get('family', '')}".strip()
                    if name:
                        authors_list.append(name)
                authors_str = ", ".join(authors_list) if authors_list else "Автор не указан"

                year = 2024
                date_parts = item.get('published-print', {}).get('date-parts', []) or item.get('published-online', {}).get('date-parts', [])
                if date_parts and date_parts[0]:
                    year = date_parts[0][0]

                category = classify_text(f"{title} {abstract}")
                doi = item.get('DOI', '')
                url_link = f"https://doi.org/{doi}" if doi else item.get('URL', 'https://scholar.google.com')

                is_russian = bool(re.search(r'[а-яА-Я]', title))

                records.append({
                    "title": title,
                    "title_original": title,
                    "summary": abstract,
                    "abstract": abstract,
                    "authors": authors_str,
                    "year": year,
                    "category": category,
                    "discipline": category,
                    "type": "Научная статья",
                    "country": "Россия" if is_russian else "Другие страны",
                    "language": "Русский" if is_russian else "Английский",
                    "url": url_link
                })
    except Exception as e:
        print(f"⚠️ Ошибка запроса к Crossref: {e}")
    
    return records

def run_collector(user_query="Olympic Games"):
    """Основной процес сбора и удаления дубликатов"""
    existing_data = load_existing_data()
    existing_titles = {item.get('title_original', item.get('title', '')).lower().strip() for item in existing_data}
    
    print(f"📦 В текущей базе данных находится {len(existing_data)} исследований.")

    new_records = []
    # Сбор из 2 крупнейших агрегаторов
    new_records.extend(fetch_openalex(user_query, limit=30))
    new_records.extend(fetch_crossref(user_query, limit=20))

    added_count = 0
    for record in new_records:
        norm_title = record['title'].lower().strip()
        if norm_title not in existing_titles:
            existing_titles.add(norm_title)
            existing_data.insert(0, record)
            added_count += 1

    print(f"✨ Найдено и добавлено новых уникальных работ: {added_count}")
    save_data(existing_data)

if __name__ == "__main__":
    import sys
    search_term = sys.argv[1] if len(sys.argv) > 1 else "Олимпийские игры олимпизм"
    run_collector(search_term)