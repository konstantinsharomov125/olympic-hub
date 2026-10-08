import json
import urllib.parse
import urllib.request
import time
import os
import re

POSSIBLE_PATHS = [
    'generated/web_data.json',
    'data/web_data.json',
    'web_data.json'
]

INPUT_FILE = None
for path in POSSIBLE_PATHS:
    if os.path.exists(path):
        INPUT_FILE = path
        break

def extract_best_title(item):
    """Умное извлечение заглавия из любых полей словаря"""
    if not isinstance(item, dict):
        return ""
    
    # 1. Сначала ищем по популярным ключам
    priority_keys = ['title', 'article', 'название', 'заглавие', 'name', 'work_title', 'Title', 'Article']
    for k in priority_keys:
        if k in item and item[k] and str(item[k]).strip() not in ['', '...', 'null', 'None']:
            return str(item[k]).strip()
            
    # 2. Если не нашли, ищем любое текстовое поле длинее 10 символов, кроме описания
    for k, v in item.items():
        if k.lower() not in ['summary', 'abstract', 'описание', 'аннотация', 'id', 'year', 'god']:
            if isinstance(v, str) and len(v.strip()) > 10:
                return v.strip()
                
    return ""

def clean_title_for_query(title):
    if not title:
        return ""
    cleaned = re.sub(r'[^\w\s]', ' ', title, flags=re.UNICODE)
    return " ".join(cleaned.split()[:12])

def search_openalex(title):
    clean_q = clean_title_for_query(title)
    if not clean_q or len(clean_q) < 5:
        return None

    encoded_q = urllib.parse.quote(clean_q)
    url = f"https://api.openalex.org/works?search={encoded_q}&per-page=1"
    headers = {'User-Agent': 'OlympicResearchPortal/1.0 (mailto:academic_project@example.com)'}
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as response:
            data = json.loads(response.read().decode('utf-8'))
            results = data.get('results', [])
            if results:
                return results[0]
    except Exception:
        pass
    return None

def search_crossref(title):
    clean_q = clean_title_for_query(title)
    if not clean_q or len(clean_q) < 5:
        return None

    encoded_q = urllib.parse.quote(clean_q)
    url = f"https://api.crossref.org/works?query.title={encoded_q}&rows=1"
    headers = {'User-Agent': 'OlympicResearchPortal/1.0 (mailto:academic_project@example.com)'}

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as response:
            data = json.loads(response.read().decode('utf-8'))
            items = data.get('message', {}).get('items', [])
            if items:
                return items[0]
    except Exception:
        pass
    return None

def rebuild_openalex_abstract(inverted_index):
    if not inverted_index:
        return ""
    word_positions = []
    for word, positions in inverted_index.items():
        for pos in positions:
            word_positions.append((pos, word))
    word_positions.sort()
    return " ".join([word for pos, word in word_positions])

def clean_html_tags(text):
    if not text:
        return ""
    return re.sub(r'<[^>]+>', '', text).strip()

def main():
    if not INPUT_FILE:
        print("❌ Файл web_data.json не найден!")
        return

    print(f"📂 Загружен файл: {INPUT_FILE}")
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    is_list = isinstance(data, list)
    dataset = data if is_list else (data.get('items') or data.get('records') or data.get('data') or [])

    if not dataset:
        print("❌ Файл пуст.")
        return

    # Вывод структуры первой записи для полной ясности
    print("\n--------------------------------------------------")
    print("📋 КЛЮЧИ ПЕРВОЙ ЗАПИСИ В ВАШЕМ JSON:")
    if isinstance(dataset[0], dict):
        for key, val in dataset[0].items():
            str_val = str(val)[:60] + "..." if len(str(val)) > 60 else str(val)
            print(f"   • {key}: {str_val}")
    print("--------------------------------------------------\n")

    updated_abstracts = 0
    updated_urls = 0
    updated_sources = 0

    print(f"🔍 Начинаем обработку {len(dataset)} записей...\n")

    for idx, item in enumerate(dataset, 1):
        title = extract_best_title(item)
        summary = str(item.get('summary') or item.get('abstract') or item.get('описание') or '')
        url = str(item.get('url') or item.get('link') or item.get('doi') or '')
        source = str(item.get('source') or item.get('journal') or item.get('источник') or '')

        needs_abstract = len(summary) < 25 or 'описание отсутст' in summary.lower()
        needs_url = not url or url in ['#', '', 'None']
        needs_source = not source or source in ['Олимпийский исследовательский портал', 'Не указан', '', 'None']

        if needs_abstract or needs_url or needs_source:
            if idx <= 5:
                print(f"[{idx}/{len(dataset)}] Заглавие: '{title[:60]}'")

            if not title or len(title) < 5:
                continue

            found_data = False

            # Поиск в OpenAlex
            alex_res = search_openalex(title)
            if alex_res:
                if needs_abstract:
                    abs_text = rebuild_openalex_abstract(alex_res.get('abstract_inverted_index'))
                    if abs_text and len(abs_text) > 20:
                        item['summary'] = abs_text
                        updated_abstracts += 1
                        found_data = True
                        print(f"   ✅ [OpenAlex] Аннотация найдена!")

                if needs_url:
                    doi = alex_res.get('doi') or alex_res.get('primary_location', {}).get('landing_page_url')
                    if doi:
                        item['url'] = doi
                        updated_urls += 1
                        found_data = True
                        print(f"   🔗 [OpenAlex] Ссылка найдена!")

                if needs_source:
                    src_name = alex_res.get('primary_location', {}).get('source', {}).get('display_name')
                    if src_name:
                        item['source'] = src_name
                        updated_sources += 1
                        found_data = True
                        print(f"   📚 [OpenAlex] Журнал найден: {src_name}")

            # Поиск в Crossref
            if not found_data:
                cross_res = search_crossref(title)
                if cross_res:
                    if needs_abstract and cross_res.get('abstract'):
                        clean_abs = clean_html_tags(cross_res.get('abstract'))
                        if len(clean_abs) > 20:
                            item['summary'] = clean_abs
                            updated_abstracts += 1
                            print(f"   ✅ [Crossref] Аннотация найдена!")

                    if needs_url and cross_res.get('URL'):
                        item['url'] = cross_res.get('URL')
                        updated_urls += 1
                        print(f"   🔗 [Crossref] Ссылка найдена!")

                    if needs_source and cross_res.get('container-title'):
                        journals = cross_res.get('container-title')
                        if journals:
                            item['source'] = journals[0]
                            updated_sources += 1
                            print(f"   📚 [Crossref] Журнал найден: {journals[0]}")

            time.sleep(0.1)

    # Сохраняем обновленный файл
    with open(INPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("\n" + "="*50)
    print("🎉 ОБРАБОТКА ЗАВЕРШЕНА!")
    print(f"📖 Заполнено аннотаций: {updated_abstracts}")
    print(f"🔗 Добавлено ссылок: {updated_urls}")
    print(f"📚 Найдено журналов: {updated_sources}")
    print("="*50)

if __name__ == '__main__':
    main()