#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест на чатбот функционалността
"""
import requests
import json
import time

BASE_URL = "http://127.0.0.1:5000"

def test_chatbot_init():
    """Тества инициализацията на чатбота"""
    print("🤖 Тестваме инициализация на чатбота...")
    
    try:
        response = requests.get(f"{BASE_URL}/chatbot/init")
        print(f"📡 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Успешна инициализация!")
            print(f"🎯 Welcome Message: {data.get('welcome_message')}")
            print(f"🔑 Session ID: {data.get('session_id')}")
            print(f"❓ Quick Questions: {data.get('quick_questions')}")
            return data.get('session_id')
        else:
            print(f"❌ Грешка: {response.status_code}")
            print(f"📄 Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"💥 Изключение: {e}")
        return None

def test_chatbot_message(session_id, message):
    """Тества изпращането на съобщение"""
    print(f"\n💬 Тестваме съобщение: '{message}'")
    
    try:
        response = requests.post(f"{BASE_URL}/chatbot/message", 
                               json={
                                   'message': message,
                                   'session_id': session_id
                               })
        
        print(f"📡 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Успешен отговор!")
            print(f"🤖 Bot Response: {data.get('message')}")
            print(f"📂 Type: {data.get('type')}")
            if data.get('category'):
                print(f"🏷️  Category: {data.get('category')}")
            if data.get('suggestions'):
                print(f"💡 Suggestions: {data.get('suggestions')}")
            return True
        else:
            print(f"❌ Грешка: {response.status_code}")
            print(f"📄 Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"💥 Изключение: {e}")
        return False

def main():
    print("🚀 Стартираме тестване на чатбота...\n")
    
    # Тест 1: Инициализация
    session_id = test_chatbot_init()
    if not session_id:
        print("❌ Не можем да инициализираме чатбота!")
        return
    
    time.sleep(1)
    
    # Тест 2: Различни въпроси
    test_messages = [
        "Как мога да се регистрирам?",
        "Какви услуги предлагате?", 
        "Безплатно ли е?",
        "В кои градове работите?",
        "Колко време отнема да получа помощ?",
        "Как да се свържа с вас?",
        "Сигурни ли са личните ми данни?",
        "Какви са изискванията за доброволци?",
        "Невалиден въпрос за тест на fallback"
    ]
    
    successful_tests = 0
    
    for message in test_messages:
        if test_chatbot_message(session_id, message):
            successful_tests += 1
        time.sleep(0.5)  # Малко почивка между тестовете
    
    # Резултати
    print(f"\n🎯 РЕЗУЛТАТИ:")
    print(f"✅ Успешни тестове: {successful_tests}/{len(test_messages)}")
    print(f"📊 Процент успешност: {(successful_tests/len(test_messages)*100):.1f}%")
    
    if successful_tests == len(test_messages):
        print("🎉 Всички тестове преминаха успешно!")
    else:
        print("⚠️  Някои тестове имат проблеми.")

if __name__ == "__main__":
    main()