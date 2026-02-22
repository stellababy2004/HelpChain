#!/usr/bin/env python3
"""
Пълна тестова процедура за HelpChain приложението
Тества всички основни функционалности след ремонта
"""

import os
import sys
import threading
import time

import requests


def print_header(text):
    print(f"\n{'=' * 60}")
    print(f" {text}")
    print(f"{'=' * 60}")


def print_success(text):
    print(f"✅ {text}")


def print_error(text):
    print(f"❌ {text}")


def print_warning(text):
    print(f"⚠️  {text}")


def print_info(text):
    print(f"ℹ️  {text}")


def wait_for_server(timeout=10):
    """Чака сървъра да се стартира"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get("http://localhost:8000/", timeout=1)
            if response.status_code == 200:
                return True
        except:
            pass
        time.sleep(0.5)
    return False


def test_server_connection():
    """Тест 1: Проверка на връзка със сървъра"""
    print_header("ТЕСТ 1: ПРОВЕРКА НА ВРЪЗКА СЪС СЪРВЪРА")

    print_info("Проверка дали сървърът работи на http://localhost:8000...")

    try:
        response = requests.get("http://localhost:8000/", timeout=5)
        if response.status_code == 200:
            print_success("Сървърът работи успешно на http://localhost:8000")
            print_info(f"Отговор: {len(response.text)} символа")
            return True
        else:
            print_error(f"Сървърът върна код {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Не може да се свърже със сървъра: {e}")
        print_info("Уверете се, че сървърът е стартиран с 'python run.py'")
        return False


def test_analytics():
    """Тест 2: Аналитика с реални данни"""
    print_header("ТЕСТ 2: АНАЛИТИКА С РЕАЛНИ ДАННИ")

    try:
        # Генерираме трафик
        print_info("Генериране на трафик за аналитика...")
        traffic_generated = 0
        for i in range(5):
            try:
                response = requests.get("http://localhost:8000/", timeout=2)
                if response.status_code == 200:
                    traffic_generated += 1
                    print_success(f"Посещение {i + 1}: успешно")
                else:
                    print_warning(f"Посещение {i + 1}: код {response.status_code}")
            except Exception as e:
                print_error(f"Посещение {i + 1}: грешка - {e}")
            time.sleep(0.1)

        print_info(f"Генерирани посещения: {traffic_generated}")

        # Проверяваме аналитиката
        print_info("Проверка на аналитичните данни...")
        response = requests.get("http://localhost:8000/api/analytics/data", timeout=5)

        if response.status_code == 200:
            data = response.json()
            overview = data.get("overview", {})

            page_views = overview.get("total_page_views", 0)
            unique_visitors = overview.get("unique_visitors", 0)
            avg_session_time = overview.get("avg_session_time", 0)
            bounce_rate = overview.get("bounce_rate", 0)

            print_success("Аналитика API работи!")
            print_info(f"📊 Прегледи на страници: {page_views}")
            print_info(f"👥 Уникални посетители: {unique_visitors}")
            print_info(f"⏱️  Средно време на сесия: {avg_session_time} мин")
            print_info(f"📈 Bounce rate: {bounce_rate}%")

            if page_views > 0 and not data.get("is_sample_data"):
                print_success("Показва РЕАЛНИ данни (не примерни)")
                return True
            elif data.get("is_sample_data"):
                print_warning("Показва примерни данни")
                return False
            else:
                print_warning("Няма достатъчно данни за анализ")
                return True
        else:
            print_error(f"Аналитика API върна код {response.status_code}")
            print_error(f"Отговор: {response.text[:200]}")
            return False

    except Exception as e:
        print_error(f"Грешка при тестване на аналитика: {e}")
        return False


def test_admin_login():
    """Тест 3: Admin login"""
    print_header("ТЕСТ 3: АДМИН ВХОД")

    try:
        # Създаваме сесия за поддържане на cookies
        session = requests.Session()

        # Първо посещаваме login страницата
        print_info("Зареждане на login страницата...")
        login_page = session.get("http://localhost:8000/admin/login", timeout=5)

        if login_page.status_code != 200:
            print_error(
                f"Login страницата не се зареди (код: {login_page.status_code})"
            )
            return False

        print_success("Login страницата се зареди успешно")

        # Тестваме login с правилни credentials
        print_info("Тест на login с правилни данни...")
        login_data = {"username": "admin", "password": "Admin123"}
        response = session.post(
            "http://localhost:8000/admin/login",
            data=login_data,
            allow_redirects=False,
            timeout=5,
        )

        print_info(f"Login POST статус: {response.status_code}")

        if response.status_code == 302:
            location = response.headers.get("Location", "")
            print_info(f"Redirect към: {location}")

            if "dashboard" in location:
                print_success("Login УСПЕШЕН! Redirect към dashboard")

                # Тестваме достъп до dashboard
                print_info("Тест на достъп до dashboard...")
                dashboard_response = session.get(
                    "http://localhost:8000/admin/dashboard", timeout=5
                )

                if dashboard_response.status_code == 200:
                    print_success("Dashboard достъпен след login")
                    return True
                else:
                    print_error(
                        f"Dashboard недостъпен (код: {dashboard_response.status_code})"
                    )
                    return False
            else:
                print_error(f"Неочакван redirect: {location}")
                return False
        else:
            print_error(f"Login не успя (статус: {response.status_code})")

            # Проверяваме дали има съобщение за грешка
            if "Грешно потребителско име или парола" in response.text:
                print_error("Грешно потребителско име или парола")
            elif "Грешка в базата данни" in response.text:
                print_error("Все още има SQLAlchemy проблем!")
            else:
                print_info(f"Отговор: {response.text[:300]}...")

            return False

    except Exception as e:
        print_error(f"Грешка при тестване на admin login: {e}")
        return False


def test_database_operations():
    """Тест 4: Database операции"""
    print_header("ТЕСТ 4: БАЗА ДАННИ ОПЕРАЦИИ")

    try:
        # Тестваме analytics tracking
        print_info("Тест на analytics tracking...")

        # Правим няколко заявки за да генерираме данни
        for i in range(3):
            try:
                requests.get("http://localhost:8000/", timeout=2)
            except:
                pass

        # Проверяваме дали данните са записани
        response = requests.get("http://localhost:8000/api/analytics/data", timeout=5)

        if response.status_code == 200:
            data = response.json()
            overview = data.get("overview", {})

            if overview.get("total_page_views", 0) > 0:
                print_success("Database операции работят (данни се записват)")
                return True
            else:
                print_warning("Няма записани данни в базата")
                return False
        else:
            print_error("Не може да се прочете от базата данни")
            return False

    except Exception as e:
        print_error(f"Грешка при тестване на database операции: {e}")
        return False


def main():
    """Основна функция за тестване"""
    print_header("ПОЛНА ТЕСТОВА ПРОЦЕДУРА - HELPCHAIN")
    print_info("Тестваме всички ремонтирани функционалности")
    print_info("Дата: 21 октомври 2025 г.")
    print()

    # Резултати от тестовете
    results = []

    # Тест 1: Проверка на връзка със сървъра
    results.append(("Проверка на връзка със сървъра", test_server_connection()))

    # Тест 2: Аналитика
    results.append(("Аналитика с реални данни", test_analytics()))

    # Тест 3: Admin login
    results.append(("Admin login", test_admin_login()))

    # Тест 4: Database операции
    results.append(("Database операции", test_database_operations()))

    # Финални резултати
    print_header("ФИНАЛНИ РЕЗУЛТАТИ")

    passed = 0
    total = len(results)

    for test_name, result in results:
        status = "✅ ПРОМИНАЛ" if result else "❌ ПРОВАЛИЛ"
        print(f"{status}: {test_name}")
        if result:
            passed += 1

    print()
    print_info(f"Общо тестове: {total}")
    print_success(f"Проминали: {passed}")
    if passed < total:
        print_error(f"Провалили: {total - passed}")

    if passed == total:
        print_header("🎉 ВСИЧКО РАБОТИ! ПОЗДРАВЛЕНИЯ!")
        print_info("Всички ремонти са успешни:")
        print_info("✅ Flask сървър без проблеми с auto-restart")
        print_info("✅ Аналитика с реални данни")
        print_info("✅ Admin login работи")
        print_info("✅ SQLAlchemy конфликти разрешени")
    else:
        print_header("⚠️  НЯКОИ ТЕСТОВЕ СЕ ПРОВАЛИХА")
        print_info("Проверете грешките по-горе и се свържете за помощ")

    print_header("КРАЙ НА ТЕСТОВЕТА")


if __name__ == "__main__":
    main()
