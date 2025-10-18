import time

import requests

time.sleep(3)

print("=== Тест на роли и права ===")
print()

try:
    # Test admin login
    session = requests.Session()
    response = session.post(
        "http://127.0.0.1:3000/admin_login",
        data={"username": "admin", "password": "admin123"},
    )
    print(f"Админ логин статус: {response.status_code}")

    if response.status_code == 302:
        print("✓ Админ логин успешен")

        # Test roles dashboard access
        response2 = session.get("http://127.0.0.1:3000/admin/roles")
        print(f"Роли dashboard статус: {response2.status_code}")

        if response2.status_code == 200:
            print("✓ Роли dashboard достъпен")
            # Check content
            content = response2.text
            if "Роли" in content and "Права" in content:
                print("✓ Съдържанието съдържа роли и права")
                print("Първи 500 символа от съдържанието:")
                print(content[:500])
            else:
                print("✗ Съдържанието не съдържа роли и права")
                print("Първи 500 символа:", content[:500])
        else:
            print(f"✗ Роли dashboard недостъпен: {response2.status_code}")
            print("Грешка:", response2.text[:300])
    else:
        print(f"✗ Админ логин неуспешен: {response.status_code}")
        print("Грешка:", response.text[:300])

except Exception as e:
    print(f"Грешка: {e}")
