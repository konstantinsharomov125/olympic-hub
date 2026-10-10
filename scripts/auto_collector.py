import os
import json

DATA_FILE = "web_data.json"

# ОБЯЗАТЕЛЬНЫЕ ОЛИМПИЙСКИЕ МАРКЕРЫ
# В названии или аннотации ДОЛЖНО быть хотя бы одно из этих слов/сочетаний:
OLYMPIC_MARKERS = [
    'олимп', 'olympic', 'олимпиад', 'olympiad',
    'паралимп', 'paralympic', 'дефлимп', 'deaflympic',
    'кубертен', 'coubertin', 'мок', 'ioc',
    'олимпийское образование', 'olympic education',
    'олимпийское движение', 'olympic movement', 
    'олимпийские игры', 'olympic games',
    'антидопинг', 'wada', 'вада'
]

def is_strictly_olympic(title, summary):
    text = (str(title) + " " + str(summary)).lower()
    
    # Проверяем, есть ли хотя бы один олимпийский маркер
    for marker in OLYMPIC_MARKERS:
        if marker in text:
            return True
            
    return False

def cleanup_and_filter():
    if not os.path.exists(DATA_FILE):
        print("⚠️ Файл базы данных web_data.json не найден.")
        return

    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    initial_count = len(data)
    
    # Оставляем только те статьи, в которых прямо упоминается олимпизм
    clean_data = []
    for item in data:
        title = item.get('title_original') or item.get('title', '')
        summary = item.get('summary') or item.get('abstract', '')
        
        if is_strictly_olympic(title, summary):
            clean_data.append(item)

    removed_count = initial_count - len(clean_data)
    print(f"🧹 Исключено посторонних работ (без олимпийских маркеров): {removed_count}")
    print(f"🥇 Осталось строго олимпийских исследований: {len(clean_data)}")

    # Сохраняем очищенную базу
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(clean_data, f, ensure_ascii=False, indent=2)

    if os.path.exists("generated"):
        with open("generated/web_data.json", 'w', encoding='utf-8') as f:
            json.dump(clean_data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    cleanup_and_filter()