import json
import os

POSSIBLE_PATHS = ['generated/web_data.json', 'data/web_data.json', 'web_data.json']
INPUT_FILE = next((p for p in POSSIBLE_PATHS if os.path.exists(p)), None)

if INPUT_FILE:
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    dataset = data if isinstance(data, list) else (data.get('items') or data.get('records') or data.get('data') or [])
    if dataset:
        print("🔍 Ключи объектов в вашей базе:", list(dataset[0].keys()))
        print("\n📄 Пример первой записи из файла:")
        print(json.dumps(dataset[0], ensure_ascii=False, indent=2)[:600])
else:
    print("❌ Файл web_data.json не найден!")