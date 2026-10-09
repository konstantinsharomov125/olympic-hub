import json
import os
import time
import numpy as np
from sentence_transformers import SentenceTransformer

POSSIBLE_PATHS = ['generated/web_data.json', 'data/web_data.json', 'web_data.json']
INPUT_FILE = next((p for p in POSSIBLE_PATHS if os.path.exists(p)), None)

# 10 категорий со смысловыми описаниями-якорями для векторного анализа
CATEGORY_DESCRIPTIONS = {
    "Олимпийское образование и просвещение": 
        "Олимпийское образование, просвещение, воспитание молодежи, ценности олимпизма в школах и вузах, педагогика спорта.",
    "Пропаганда, философия и культурология": 
        "Философия олимпизма, Кубертен, культурология, ценности спорта, идеалы, олимпийское движение в искусстве и культуре.",
    "История и наследие олимпизма": 
        "История олимпийских игр, древняя Олимпия, наследие прошлых игр, архивные исследования, эволюция видов спорта.",
    "Этика, честная игра и антидопинг": 
        "Этика, Fair Play, честная игра, борьба с допингом, юридические коллизии, гендерные верификации, дисквалификации, спортивное право.",
    "Политика, геополитика и глобальные вызовы": 
        "Политика и спорт, бойкоты, геополитические вызовы, санкции, МОК и государства, международные отношения.",
    "Психология олимпийского спорта": 
        "Психологическая подготовка спортсменов, стресс, мотивация, ментальное здоровье, психопрофилактика, психология побед.",
    "Менеджмент, маркетинг и экономика Игр": 
        "Менеджмент, маркетинг, экономический эффект Игр, кибербезопасность, организация соревнований, спонсорство, инфраструктура.",
    "Спортивная медицина, физиология и биомеханика": 
        "Спортивная медицина, биомеханика, физиология, VO2max, травматология, реабилитация, функциональная диагностика.",
    "Подготовка олимпийского резерва и тренировка": 
        "Тренировочный процесс, подготовка резерва, методики тренировок, спортивный отбор, юношеский спорт, физические качества.",
    "Теория и методология олимпийского движения": 
        "Теория спортивной тренировки, методология исследований, системные подходы к спорту высших достижений, структуры подготовки."
}

cat_names = list(CATEGORY_DESCRIPTIONS.keys())
cat_texts = list(CATEGORY_DESCRIPTIONS.values())

def extract_text(item):
    if not isinstance(item, dict):
        return ""
    title = str(item.get('title_original') or item.get('title') or item.get('article') or '').strip()
    summary = str(item.get('summary') or item.get('abstract') or item.get('description') or '').strip()
    return f"{title}. {summary}".strip()

def main():
    if not INPUT_FILE:
        print("❌ Файл web_data.json не найден!")
        return

    print("🧠 Загрузка локальной нейросети (paraphrase-multilingual-MiniLM-L12-v2)...")
    # При первом запуске модель скачается один раз (~470 МБ)
    model = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')

    print("📐 Векторизация 10 олимпийских категорий...")
    cat_embeddings = model.encode(cat_texts, normalize_embeddings=True)

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    dataset = data if isinstance(data, list) else (data.get('items') or data.get('records') or data.get('data') or [])

    print(f"📂 Загружено исследований: {len(dataset)}")
    print("🚀 Начинаем векторный анализ...")

    start_time = time.time()
    updated_count = 0

    texts_to_encode = []
    valid_indices = []

    for idx, item in enumerate(dataset):
        text = extract_text(item)
        if len(text) > 5:
            texts_to_encode.append(text[:1000])
            valid_indices.append(idx)

    # Пакетная векторизация всех статей
    doc_embeddings = model.encode(
        texts_to_encode, 
        batch_size=64, 
        show_progress_bar=True, 
        normalize_embeddings=True
    )

    # Косинусное сходство векторов статей и векторов категорий
    similarities = np.dot(doc_embeddings, cat_embeddings.T)

    for i, idx in enumerate(valid_indices):
        best_cat_idx = int(np.argmax(similarities[i]))
        best_category = cat_names[best_cat_idx]

        dataset[idx]['category'] = best_category
        dataset[idx]['discipline'] = best_category
        updated_count += 1

    with open(INPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print(f"🎉 КЛАССИФИКАЦИЯ УСПЕШНО ЗАВЕРШЕНА ЗА {elapsed:.2f} СЕК!")
    print(f"📊 Точно размечено работ: {updated_count} из {len(dataset)}")
    print(f"💾 Данные сохранены в: {INPUT_FILE}")
    print("=" * 60)

if __name__ == '__main__':
    main()