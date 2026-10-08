import json
import os

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

# Расширенная карта 10 олимпийских направлений и подстрочных ключей (RU + EN)
CATEGORY_PATTERNS = {
    'Олимпийское образование и просвещение': [
        'образован', 'педагог', 'воспитан', 'учеб', 'школ', 'вуз', 'студент', 'академи', 'просвещен', 'преподав',
        'educat', 'pedagog', 'school', 'curriculum', 'university', 'student', 'teaching', 'academy', 'learning'
    ],
    'Пропаганда, философия и культурология': [
        'пропаганд', 'популяриз', 'сми', 'медиа', 'культур', 'философ', 'идеал', 'ценност', 'символ', 'искусств', 'гуманизм',
        'media', 'journalism', 'press', 'broadcast', 'culture', 'philosophy', 'value', 'ideals', 'symbol', 'art', 'humanism'
    ],
    'История и наследие олимпизма': [
        'истор', 'наслед', 'традиц', 'кубертен', 'древн', 'музей', 'архив', 'памят', 'эволюц', 'ретроспек',
        'histor', 'legacy', 'heritage', 'coubertin', 'ancient', 'archival', 'museum', 'tradition', 'evolution'
    ],
    'Этика, честная игра и антидопинг': [
        'этик', 'допинг', 'fair play', 'честн', 'прав', 'юриспруд', 'закон', 'коррупц', 'суд', 'вада', 'wada',
        'ethic', 'doping', 'anti-doping', 'fair play', 'law', 'legal', 'integrity', 'corruption', 'court'
    ],
    'Политика, геополитика и глобальные вызовы': [
        'политик', 'кризис', 'коммерц', 'санкц', 'бойкот', 'геополитик', 'конфликт', 'дипломат', 'протест', 'нейтральн',
        'politic', 'boycott', 'crisis', 'commercial', 'sanction', 'geopolitic', 'conflict', 'protest', 'diplomacy'
    ],
    'Психология олимпийского спорта': [
        'психолог', 'стресс', 'мотивац', 'эмоц', 'личность', 'тревож', 'ментальн', 'психофизио', 'настрой',
        'psychol', 'stress', 'motivat', 'anxiety', 'mental', 'emotional', 'coping', 'personality', 'mindset'
    ],
    'Менеджмент, маркетинг и экономика Игр': [
        'менедж', 'эконом', 'управлен', 'маркетинг', 'спонсор', 'инфраструктур', 'бюджет', 'туризм', 'бизнес', 'финанс',
        'manag', 'econom', 'market', 'sponsor', 'infrastruct', 'budget', 'finance', 'tourism', 'business'
    ],
    'Спортивная медицина, физиология и биомеханика': [
        'медицин', 'физиолог', 'биомехан', 'травм', 'реабилит', 'восстановл', 'сердеч', 'мышц', 'биохим', 'морфолог', 'диагност',
        'medicin', 'physiol', 'biomechan', 'injury', 'rehabit', 'recovery', 'cardio', 'muscle', 'biochem', 'morphol', 'diagnost'
    ],
    'Подготовка олимпийского резерва и тренировка': [
        'подготовк', 'трениров', 'резерв', 'отбор', 'нагруз', 'методик', 'соревнован', 'качества', 'вынослив', 'сила', 'скорост',
        'train', 'prep', 'reserve', 'selection', 'load', 'methodolog', 'endurance', 'strength', 'speed', 'athlete'
    ],
    'Теория и методология олимпийского движения': [
        'теория', 'методол', 'концепц', 'структур', 'систем', 'модель', 'перспектив', 'развити', 'олимпизм', 'движени',
        'theory', 'methodology', 'concept', 'structure', 'system', 'model', 'perspective', 'development', 'olympism'
    ]
}

def classify_text(title, summary):
    full_text = f"{title} {summary}".lower()
    scores = {cat: 0 for cat in CATEGORY_PATTERNS}
    
    # Прямой поиск вхождений основы слова в тексте
    for cat, keywords in CATEGORY_PATTERNS.items():
        for kw in keywords:
            count = full_text.count(kw.lower())
            scores[cat] += count

    best_cat = max(scores, key=scores.get)
    
    # Если точных совпадений нет, относим к теоретико-методологическим основам
    if scores[best_cat] == 0:
        return 'Теория и методология олимпийского движения'
        
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

    print(f"🧠 Начинаем переклассификацию {len(dataset)} исследований...\n")

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
    print("📊 Новое распределение исследований по 10 направлениям:")
    for cat, count in sorted(stats.items(), key=lambda x: x[1], reverse=True):
        print(f"   • {cat}: {count}")
    print("="*50)

if __name__ == '__main__':
    main()