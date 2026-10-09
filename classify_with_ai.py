import json
import os
import time
from google import genai

POSSIBLE_PATHS = ['generated/web_data.json', 'data/web_data.json', 'web_data.json']
INPUT_FILE = next((p for p in POSSIBLE_PATHS if os.path.exists(p)), None)

MODEL_NAME = 'gemini-3.8-flash'

CATEGORIES = [
    "Олимпийское образование и просвещение",
    "Пропаганда, философия и культурология",
    "История и наследие олимпизма",
    "Этика, честная игра и антидопинг",
    "Политика, геополитика и глобальные вызовы",
    "Психология олимпийского спорта",
    "Менеджмент, маркетинг и экономика Игр",
    "Спортивная медицина, физиология и биомеханика",
    "Подготовка олимпийского резерва и тренировка",
    "Теория и методология олимпийского движения"
]

PROMPT_TEMPLATE = """Проанализируй заглавие и аннотацию научной работы по олимпийской тематике и определи, к какому из 10 направлений она относится строго смыслово.

Список допустимых категорий:
1. Олимпийское образование и просвещение
2. Пропаганда, философия и культурология
3. История и наследие олимпизма
4. Этика, честная игра и антидопинг
5. Политика, геополитика и глобальные вызовы
6. Психология олимпийского спорта
7. Менеджмент, маркетинг и экономика Игр
8. Спортивная медицина, физиология и биомеханика
9. Подготовка олимпийского резерва и тренировка
10. Теория и методология олимпийского движения

Данные работы:
- Заглавие: {title}
- Аннотация: {summary}

В ответе напиши ТОЛЬКО название выбранной категории из списка выше (без лишних слов, кавычек и номеров)."""

def extract_title_and_summary(item):
    if not isinstance(item, dict):
        return "", ""
    
    title_keys = ['title_original', 'title', 'title_ru', 'title_en', 'article', 'article_title', 'paper_title', 'name']
    summary_keys = ['summary', 'abstract', 'annotation', 'description', 'desc', 'summary_ru', 'text']
    
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

def call_gemini_with_retry(client, prompt, max_retries=5):
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
            )
            return response.text
        except Exception as e:
            err_msg = str(e)
            if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg or "Quota" in err_msg:
                wait_time = 12 * (attempt + 1)
                print(f"\n ⏳ Лимит запросов. Ждем {wait_time} сек...")
                time.sleep(wait_time)
            else:
                if attempt == max_retries - 1:
                    raise e
                time.sleep(4)
    raise Exception("Превышено число попыток обращения к Gemini API")

def main():
    if not INPUT_FILE:
        print("❌ Файл web_data.json не найден!")
        return

    # Запрос ключа через переменную или ввод пользователя (без сохранения в коде)
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        api_key = input("🔑 Введите ваш Gemini API Key: ").strip()

    if not api_key:
        print("❌ API ключ не передан!")
        return

    client = genai.Client(api_key=api_key)

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    dataset = data if isinstance(data, list) else (data.get('items') or data.get('records') or data.get('data') or [])

    print(f"📂 Загружено записей: {len(dataset)}")
    print(f"🤖 Начинаем классификацию через модель {MODEL_NAME}...\n")

    updated_count = 0

    for idx, item in enumerate(dataset, 1):
        title, summary = extract_title_and_summary(item)

        if not title and not summary:
            continue

        try:
            prompt = PROMPT_TEMPLATE.format(
                title=title if title else "Не указано", 
                summary=summary[:400] if summary else "Аннотация отсутствует"
            )
            
            raw_text = call_gemini_with_retry(client, prompt)
            ai_category = raw_text.strip().replace('"', '').replace("'", "")

            matched_cat = next((c for c in CATEGORIES if c.lower() in ai_category.lower()), None)
            
            if matched_cat:
                item['category'] = matched_cat
                item['discipline'] = matched_cat
                updated_count += 1
                print(f"[{idx}/{len(dataset)}] ✅ '{(title or summary)[:35]}...' -> {matched_cat}")

            time.sleep(4.2)

        except Exception as e:
            print(f"[{idx}/{len(dataset)}] ❌ Ошибка: {e}")
            time.sleep(4)

        if updated_count > 0 and updated_count % 10 == 0:
            with open(INPUT_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

    with open(INPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("\n" + "="*50)
    print(f"🎉 КЛАССИФИКАЦИЯ ЗАВЕРШЕНА!")
    print(f"📊 Обработано работ: {updated_count} из {len(dataset)}")
    print("="*50)

if __name__ == '__main__':
    main()