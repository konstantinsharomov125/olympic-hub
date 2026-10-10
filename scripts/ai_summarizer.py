import os
import json

DATA_FILE = "web_data.json"

def process_summaries():
    if not os.path.exists(DATA_FILE):
        print("⚠️ Файл с данными не найден.")
        return

    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    updated = False
    
    for item in data:
        # Получаем оригинальную аннотацию или описание
        summary = item.get('summary') or item.get('abstract', '')
        title = item.get('title_original') || item.get('title', '')
        
        # Если аннотация пустая или требует оформления
        if not item.get('ai_processed'):
            if summary and len(summary) > 15:
                # Очищаем и сохраняем текст аннотации для карточки
                item['summary_ru'] = summary
            else:
                item['summary_ru'] = f"Научная работа посвящена исследованию актуальных проблем в области физической культуры и олимпийского движения по теме: «{title}»."
            
            item['ai_processed'] = True
            updated = True

    if updated:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        if os.path.exists("generated"):
            with open("generated/web_data.json", 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
        print("✅ Обработка аннотаций успешно завершена!")
    else:
        print("ℹ️ Нет новых записей для обработки.")

if __name__ == "__main__":
    process_summaries()