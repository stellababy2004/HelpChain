#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🔧 Тест за analytics route
"""

import sys

sys.path.append(".")

from appy import app, db
from admin_analytics import AnalyticsEngine, RequestFilter, RealtimeUpdates
from datetime import datetime
from models import HelpRequest, Volunteer


def test_analytics_route():
    """Тестваме analytics route кода директно"""

    with app.app_context():
        print("🔍 Тествам analytics route логиката...")

        try:
            # Получаваме статистики
            print("1. Получавам dashboard stats...")
            stats = AnalyticsEngine.get_dashboard_stats(days=30)
            print(f"   ✅ Stats: {type(stats)} with keys: {list(stats.keys())}")
            print(f"   Category stats: {stats.get('category_stats', 'НЯМА')}")

            # Филтрираме заявки
            print("2. Филтрирам заявки...")
            filtered_requests = RequestFilter.filter_requests(
                status=None,
                date_from=None,
                date_to=None,
                location=None,
                keyword=None,
                category=None,
                page=1,
                per_page=20,
            )
            print(f"   ✅ Filtered: {type(filtered_requests)}")

            # Получаваме опции за филтри
            print("3. Получавам filter options...")
            filter_options = RequestFilter.get_filter_options()
            print(f"   ✅ Filter options: {type(filter_options)}")

            # Геолокационни данни
            print("4. Получавам geo data...")
            geo_data = AnalyticsEngine.get_geo_data()
            print(f"   ✅ Geo data: {type(geo_data)}")

            # Последна активност
            print("5. Получавам recent activity...")
            recent_activity = RealtimeUpdates.get_recent_activity(limit=10)
            print(f"   ✅ Recent activity: {type(recent_activity)}")

            # Допълнителни статистики
            print("6. Изчислявам допълнителни статистики...")
            success_rate = AnalyticsEngine.get_success_rate()
            print(f"   ✅ Success rate: {success_rate}")

            today_requests = HelpRequest.query.filter(
                db.func.date(HelpRequest.created_at) == datetime.utcnow().date()
            ).count()
            print(f"   ✅ Today requests: {today_requests}")

            # Най-активен доброволец
            print("7. Търся най-активен доброволец...")
            top_volunteer = Volunteer.query.first()
            print(f"   ✅ Top volunteer: {top_volunteer}")

            # ПРОБЛЕМЕН КОД - Най-честа категория
            print("8. Изчислявам най-честа категория...")
            print(f"   Category stats type: {type(stats['category_stats'])}")
            print(f"   Category stats content: {stats['category_stats']}")

            if stats["category_stats"] and len(stats["category_stats"]) > 0:
                print("   Имаме category stats...")
                items = stats["category_stats"].items()
                print(f"   Items type: {type(items)}")
                print(f"   Items content: {list(items)}")

                # Тестваме max функцията
                if list(items):
                    top_category = max(
                        stats["category_stats"].items(), key=lambda x: x[1]
                    )[0]
                    print(f"   ✅ Top category: {top_category}")
                else:
                    top_category = "Няма данни"
                    print("   ⚠️ No items in category stats")
            else:
                top_category = "Няма данни"
                print("   ⚠️ No category stats")

            print("\n🎉 Всички тестове преминаха успешно!")

        except Exception as e:
            print(f"\n❌ ГРЕШКА: {e}")
            import traceback

            traceback.print_exc()


if __name__ == "__main__":
    test_analytics_route()
