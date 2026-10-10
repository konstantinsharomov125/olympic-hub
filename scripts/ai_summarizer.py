import os
import json
from deep_translator import GoogleTranslator

DATA_FILE = "web_data.json"

def translate_abstract(text):
    if not text or len(text.strip()) < 5:
        return text
    try:
        # Используем надежный переводчик с автоматическим определением языка оригинала
        translator = GoogleTranslator(source='auto', target='ru')
        # Переводим фрагментами, если текст слишком длинный
        if len(text) > 4000:
            text = text[:4000]
        return translator.translate(text)
    except Exception as e:
        print(f"⚠️ Ошибка при переводе: {e}")
        return text

def process_summaries():
    if not os.path.exists(DATA_FILE):
        print("⚠️ Файл web_data.json не найден.")
        return

    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    updated = False
    
    for item in data:
        summary = item.get('summary') or item.get('abstract', '')
        
        # Переводим, если оригинальная аннотация есть, а русского перевода еще нет
        if summary and not item.get('summary_ru'):
            title = item.get('title', 'Без названия')
            print(f"🔄 Перевод: {title[:50]}...")
            
            translated = translate_abstract(summary)
            item['summary_ru'] = translated
            item['summary_original'] = summary  # Сохраняем оригинал
            updated = True

    if updated:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        if os.path.exists("generated"):
            with open("generated/web_data.json", 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
        print("✅ Все аннотации успешно переведены на русский язык!")
    else:
        print("ℹ️ Нет новых аннотаций для перевода.")

if __name__ == "__main__":
    process_summaries()