import json
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

CATEGORY_PATTERNS = {
    'Олимпийское образование и просвещение': [
        'образован', 'педагог', 'воспитан', 'учеб', 'школ', 'вуз', 'студент', 'академи',
        'educat', 'pedagog', 'school', 'curriculum', 'university', 'student', 'teaching', 'academy'
    ],
    'Пропаганда и идеалы олимпизма': [
        'пропаганд', 'популяриз', 'сми', 'медиа', 'культур', 'философ', 'идеал', 'ценност',
        'media', 'journalism', 'press', 'broadcast', 'culture', 'philosophy', 'value', 'ideals', 'symbol'
    ],
    'История и наследие олимпизма': [
        'истор', 'наслед', 'традиц', 'кубертен', 'древн', 'музей', 'архив', 'памят',
        'histor', 'legacy', 'heritage', 'coubertin', 'ancient', 'archival', 'museum', 'tradition'
    ],
    'Этика, честная игра и антидопинг': [
        'этик', 'допинг', 'fair play', 'честн', 'прав', 'юриспруд', 'закон', 'коррупц', 'суд',
        'ethic', 'doping', 'wada', 'anti-doping', 'fair play', 'law', 'legal', 'integrity', 'corruption'
    ],
    'Проблемы и вызовы олимпизма': [
        'проблем', 'политик', 'кризис', 'коммерц', 'санкц', 'бойкот', 'геополитик', 'конфликт',
        'politic', 'boycott', 'crisis', 'commercial', 'sanction', 'geopolitic', 'conflict', 'protest'
    ],
    'Психология олимпийского спорта': [
        'психолог', 'стресс', 'мотивац', 'эмоц', 'личность', 'тревож', 'ментальн',
        'psychol', 'stress', 'motivat', 'anxiety', 'mental', 'emotional', 'coping', 'personality'
    ],
    'Менеджмент и экономика Игр': [
        'менедж', 'эконом', 'управлен', 'маркетинг', 'спонсор', 'инфраструктур', 'бюджет', 'туризм',
        'manag', 'econom', 'market', 'sponsor', 'infrastruct', 'budget', 'finance', 'tourism', 'business'
    ],
    'Подготовка олимпийского резерва': [
        'подготовк', 'трениров', 'физиолог', 'биомехан', 'отбор', 'нагруз', 'методик', 'соревнован',
        'train', 'prep', 'physiol', 'biomechan', 'performance', 'athlete', 'coach', 'testing', 'selection'
    ]
}

def classify_text(title, summary):
    full_text = f"{title} {summary}".lower()
    scores = {cat: 0 for cat in CATEGORY_PATTERNS}
    
    for cat, keywords in CATEGORY_PATTERNS.items():
        for kw in keywords:
            matches = len(re.findall(r'\b' + re.escape(kw), full_text))
            scores[cat] += matches

    best_cat = max(scores, key=scores.get)
    if scores[best_cat] == 0:
        return 'Другие темы олимпизма'
        
    return best_cat

def main():
    if not INPUT_FILE:
        print("❌ Файл web_data.json не найден!")
        return

    print(f"📂 Загружен файл: {INPUT_FILE}")
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    is_list = isinstance(data, list)
    dataset = data if is_list else (data.get('items') or data.get('records') or data.get('data') or [])

    classified_count = 0
    stats = {}

    print(f"🧠 Начинаем классификацию {len(dataset)} исследований...\n")

    for item in dataset:
        title = str(item.get('title') or item.get('article') or '')
        summary = str(item.get('summary') or item.get('abstract') or '')

        new_cat = classify_text(title, summary)
        item['category'] = new_cat
        item['discipline'] = new_cat
        
        stats[new_cat] = stats.get(new_cat, 0) + 1
        classified_count += 1

    with open(INPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("="*50)
    print(f"🎉 КЛАССИФИКАЦИЯ УСПЕШНО ЗАВЕРШЕНА ({classified_count} записей)!\n")
    print("📊 Распределение исследований по направлениям:")
    for cat, count in sorted(stats.items(), key=lambda x: x[1], reverse=True):
        print(f"   • {cat}: {count}")
    print("="*50)

if __name__ == '__main__':
    main()