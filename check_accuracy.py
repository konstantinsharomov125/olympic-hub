import json
import os
import random

POSSIBLE_PATHS = ['generated/web_data.json', 'data/web_data.json', 'web_data.json']
INPUT_FILE = next((p for p in POSSIBLE_PATHS if os.path.exists(p)), None)

def extract_title_and_summary(item):
    if not isinstance(item, dict):
        return "", ""
    
    title_keys = ['title_original', 'title', 'title_ru', 'title_en', 'article', 'article_title', 'paper_title', 'name', 'header', 'heading']
    summary_keys = ['summary', 'abstract', 'annotation', 'description', 'desc', 'summary_ru', 'text', 'content']
    
    title = ""
    for k in title_keys:
        val = item.get(k)
        if val and isinstance(val, str) and len(val.strip()) > 0:
            title = val.strip()
            break

    summary = ""
    for k in summary_keys:
        val = item.get(k)
        if val and isinstance(val, str) and len(val.strip()) > 0:
            summary = val.strip()
            break

    return title, summary

def audit_dataset(samples=15):
    if not INPUT_FILE:
        print("❌ Файл web_data.json не найден!")
        return

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    dataset = data if isinstance(data, list) else (data.get('items') or data.get('records') or data.get('data') or [])

    if not dataset:
        print("❌ Не удалось найти записи в файле!")
        return

    sample_items = random.sample(dataset, min(samples, len(dataset)))

    print("=" * 80)
    print(f"📊 АУДИТ КАЧЕСТВА КЛАССИФИКАЦИИ ({len(sample_items)} из {len(dataset)} работ)")
    print("=" * 80 + "\n")

    for idx, item in enumerate(sample_items, 1):
        title, summary = extract_title_and_summary(item)
        category = item.get('category') or item.get('discipline') or 'Не указана'

        print(f"[{idx}] 📌 ЗАГЛАВИЕ: {title if title else 'Не найдено'}")
        print(f"    🏷️  КАТЕГОРИЯ:  {category}")
        print(f"    📖 АННОТАЦИЯ: {(summary[:150] + '...') if summary else 'Описание отсутствует'}\n")
        print("-" * 80)

if __name__ == '__main__':
    audit_dataset(15)