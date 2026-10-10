import os
import json
import random
import requests

VK_BOT_TOKEN = os.environ.get("VK_BOT_TOKEN")
VK_USER_ID = os.environ.get("VK_USER_ID")
DATA_FILE = "web_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def send_vk_message(user_id, text):
    """Отправка личного сообщения от имени сообщества VK"""
    if not VK_BOT_TOKEN or not user_id:
        print("⚠️ Переменные VK_BOT_TOKEN или VK_USER_ID не найдены.")
        return False
        
    url = "https://api.vk.com/method/messages.send"
    params = {
        "user_id": user_id,
        "message": text,
        "random_id": random.randint(1, 2147483647),
        "access_token": VK_BOT_TOKEN,
        "v": "5.131"
    }
    try:
        res = requests.post(url, data=params, timeout=10)
        result = res.json()
        if "response" in result:
            print("✅ Отчёт успешно отправлен в личные сообщения ВКонтакте!")
            return True
        else:
            print(f"⚠️ Ошибка VK API: {result.get('error')}")
            return False
    except Exception as e:
        print(f"⚠️ Ошибка сети при отправке в VK: {e}")
        return False

def generate_weekly_report():
    """Формирование сводки еженедельного обновления базы"""
    data = load_data()
    total = len(data)
    recent = data[:5]
    
    report = f"📊 Еженедельный отчёт Олимпийского портала\n\n"
    report += f"✅ Всего исследований в базе: {total}\n\n"
    report += "🆕 Последние добавленные работы:\n"
    for i, item in enumerate(recent, 1):
        report += f"{i}. {item.get('title')} ({item.get('year')})\n"
        
    report += f"\n🌐 Перейти на портал: https://konstantinsharomov125.github.io/olympic-hub/"
    return report

if __name__ == "__main__":
    if VK_BOT_TOKEN and VK_USER_ID:
        report_text = generate_weekly_report()
        send_vk_message(VK_USER_ID, report_text)
    else:
        print("ℹ️ Скрипт готов к запуску через GitHub Actions.")