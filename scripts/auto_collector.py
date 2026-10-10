import os
import json

DATA_FILE = "web_data.json"

# 1. СТРОГИЙ СПИСОК ОЛИМПИЙСКИХ КЛЮЧЕВЫХ СЛОВ (Хотя бы одно должно присутствовать!)
OLYMPIC_KEYWORDS = [
    'олимп', 'olympic', 'олимпиад', 'olympiad',
    'паралимп', 'paralympic', 'дефлимп', 'deaflympic',
    'кубертен', 'coubertin', 'мок', 'ioc',
    'олимпийск', 'олимпийское образование', 'olympic education',
    'олимпийское движение', 'olympic movement', 'олимпийские игры', 'olympic games',
    'антидопинг', 'wada', 'вада'
]

# 2. РАСШИРЕННЫЙ СПИСОК СТОП-СЛОВ (Исключаем посторонние гуманитарные/бытовые темы)
STOP_KEYWORDS = [
    'речевой этикет', 'лингвистик', 'грамматик', 'синтаксис', 
    'фольклор', 'литературоведен', 'поэтик', 'фразеологизм',
    'терминология', 'языкознан', 'дидактика языка', 'орфографи',
    'методика преподавания русского', 'художественная литература'
]

def is_strictly_olympic(title, summary):
    text = (str(title) + " " + str(summary)).lower()
    
    # 1. Проверка на стоп-слова
    for stop_word in STOP_KEYWORDS:
        if stop_word in text:
            return False
            
    # 2. Строгая проверка на наличие олимпийской тематики
    for keyword in OLYMPIC_KEYWORDS:
        if keyword in text:
            return True
            
    return False

def cleanup_and_filter():
    if not os.path.exists(DATA_FILE):
        print("⚠️ Файл базы данных web_data.json не найден.")
        return

    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    initial_count = len(data)
    
    # Отбираем только работы, соответствующие строгой олимпийской тематике
    clean_data = []
    for item in data:
        title = item.get('title_original') or item.get('title', '')
        summary = item.get('summary') or item.get('abstract', '')
        
        if is_strictly_olympic(title, summary):
            clean_data.append(item)

    removed_count = initial_count - len(clean_data)
    print(f"🧹 Исключено неолимпийских работ: {removed_count}")
    print(f"🥇 Осталось строго олимпийских исследований: {len(clean_data)}")

    # Сохраняем очищенную базу
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(clean_data, f, ensure_ascii=False, indent=2)

    if os.path.exists("generated"):
        with open("generated/web_data.json", 'w', encoding='utf-8') as f:
            json.dump(clean_data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    cleanup_and_filter()