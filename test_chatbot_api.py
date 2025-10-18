import requests

BASE_URL = "http://localhost:5000"

print("🔄 Тестване на chatbot API...")

# Тест 1: Основен въпрос
print("\n1. Тест с основен въпрос:")
try:
    response = requests.post(
        f"{BASE_URL}/api/chatbot/message",
        json={"message": "Здравей, какво е HelpChain?"},
        timeout=30,
    )
    if response.status_code == 200:
        data = response.json()
        print("✅ Отговор:", data.get("response", "Няма отговор"))
        print("📊 Provider:", data.get("provider", "Неизвестен"))
        print("🎯 Confidence:", data.get("confidence", "Няма"))
    else:
        print("❌ HTTP грешка:", response.status_code, response.text)
except Exception as e:
    print("❌ Грешка:", str(e))

# Тест 2: Въпрос за доброволчество
print("\n2. Тест с въпрос за доброволчество:")
try:
    response = requests.post(
        f"{BASE_URL}/api/chatbot/message",
        json={"message": "Как да стана доброволец?"},
        timeout=30,
    )
    if response.status_code == 200:
        data = response.json()
        print("✅ Отговор:", data.get("response", "Няма отговор"))
        print("📊 Provider:", data.get("provider", "Неизвестен"))
    else:
        print("❌ HTTP грешка:", response.status_code, response.text)
except Exception as e:
    print("❌ Грешка:", str(e))

# Тест 3: Въпрос за цени
print("\n3. Тест с въпрос за цени:")
try:
    response = requests.post(
        f"{BASE_URL}/api/chatbot/message",
        json={"message": "Колко струва помощта в домакинството?"},
        timeout=30,
    )
    if response.status_code == 200:
        data = response.json()
        print("✅ Отговор:", data.get("response", "Няма отговор"))
        print("📊 Provider:", data.get("provider", "Неизвестен"))
    else:
        print("❌ HTTP грешка:", response.status_code, response.text)
except Exception as e:
    print("❌ Грешка:", str(e))

print("\n✨ Chatbot API тестове завършени!")
