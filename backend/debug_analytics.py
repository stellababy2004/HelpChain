#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🔧 Debug скрипт за Analytics проблеми
====================================
"""

import sys
import os

sys.path.append(".")

# Добавяме пътя на приложението
os.chdir(
    r"c:\Users\Stella Barbarella\OneDrive\Documents\chatGPT\Projet BG\HelpChain\backend"
)


def test_imports():
    """Тестваме import-ите"""
    print("🔍 Тествам import-ите...")

    try:
        print("✅ appy import - OK")
    except Exception as e:
        print(f"❌ appy import error: {e}")
        return False

    try:
        print("✅ admin_analytics import - OK")
    except Exception as e:
        print(f"❌ admin_analytics import error: {e}")
        return False

    try:
        print("✅ models import - OK")
    except Exception as e:
        print(f"❌ models import error: {e}")
        return False

    return True


def test_database():
    """Тестваме database-а"""
    print("\n🗄️ Тествам database-а...")

    try:
        from appy import app
        from models import HelpRequest, Volunteer

        with app.app_context():
            # Тестваме основни заявки
            request_count = HelpRequest.query.count()
            volunteer_count = Volunteer.query.count()

            print("✅ Database connection - OK")
            print(f"📊 Help Requests: {request_count}")
            print(f"👥 Volunteers: {volunteer_count}")

            return True
    except Exception as e:
        print(f"❌ Database error: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_analytics_functions():
    """Тестваме analytics функциите"""
    print("\n📊 Тествам analytics функциите...")

    try:
        from appy import app
        from admin_analytics import AnalyticsEngine, RequestFilter, RealtimeUpdates

        with app.app_context():
            print("🔍 Тествам AnalyticsEngine.get_dashboard_stats()...")
            stats = AnalyticsEngine.get_dashboard_stats(days=30)
            print(f"✅ Dashboard stats: {type(stats)} with {len(stats)} keys")

            print("🔍 Тествам RequestFilter.filter_requests()...")
            filtered = RequestFilter.filter_requests(page=1, per_page=5)
            print(f"✅ Filter requests: {type(filtered)} with {len(filtered)} keys")

            print("🔍 Тествам AnalyticsEngine.get_geo_data()...")
            geo_data = AnalyticsEngine.get_geo_data()
            print(f"✅ Geo data: {type(geo_data)} with {len(geo_data)} keys")

            print("🔍 Тествам RealtimeUpdates.get_recent_activity()...")
            activity = RealtimeUpdates.get_recent_activity(limit=5)
            print(f"✅ Recent activity: {type(activity)} with {len(activity)} items")

            return True
    except Exception as e:
        print(f"❌ Analytics functions error: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_web_request():
    """Тестваме web заявката"""
    print("\n🌐 Тествам web заявката...")

    try:
        import requests
        import time

        # Чакаме малко за Flask да стартира
        time.sleep(2)

        session = requests.Session()

        # Тестваме login
        print("🔐 Тествам login...")
        login_data = {"username": "admin", "password": "help2025!"}
        login_response = session.post(
            "http://127.0.0.1:5000/admin_login", data=login_data, timeout=10
        )
        print(f"Login response: {login_response.status_code}")

        # Тестваме analytics
        print("📊 Тествам analytics page...")
        analytics_response = session.get(
            "http://127.0.0.1:5000/admin/analytics", timeout=10
        )
        print(f"Analytics response: {analytics_response.status_code}")

        if analytics_response.status_code != 200:
            print("Response headers:", dict(analytics_response.headers))
            print("Response text (first 500 chars):")
            print(analytics_response.text[:500])
        else:
            print("✅ Analytics page loads successfully!")

        return analytics_response.status_code == 200

    except Exception as e:
        print(f"❌ Web request error: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Главна debug функция"""
    print("🚀 HelpChain Analytics Debug Tool")
    print("=" * 50)

    success = True

    # Test 1: Imports
    if not test_imports():
        success = False

    # Test 2: Database
    if not test_database():
        success = False

    # Test 3: Analytics Functions
    if not test_analytics_functions():
        success = False

    # Test 4: Web Request
    if not test_web_request():
        success = False

    print("\n" + "=" * 50)
    if success:
        print("🎉 Всички тестове преминаха успешно!")
        print("✅ Analytics системата работи правилно!")
    else:
        print("❌ Има проблеми, които трябва да се поправят.")

    print("=" * 50)


if __name__ == "__main__":
    main()
