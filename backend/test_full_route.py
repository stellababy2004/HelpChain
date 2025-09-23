#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🔧 Директен тест на analytics route
"""

import sys

sys.path.append(".")


def test_full_analytics_route():
    """Тестваме пълния analytics route"""

    from appy import app

    with app.test_client() as client:
        with app.app_context():
            # Симулираме login session
            with client.session_transaction() as sess:
                sess["admin_logged_in"] = True

            print("🔍 Тествам пълния analytics route...")

            try:
                # Правим заявка към analytics endpoint
                response = client.get("/admin/analytics")

                print(f"Status Code: {response.status_code}")
                print(f"Content-Type: {response.content_type}")

                if response.status_code == 200:
                    print("✅ Analytics route работи успешно!")
                    print(f"Response length: {len(response.data)} bytes")
                else:
                    print(f"❌ Analytics route върна грешка: {response.status_code}")
                    print("Response data (first 500 chars):")
                    print(response.data.decode("utf-8")[:500])

            except Exception as e:
                print(f"❌ Грешка в route: {e}")
                import traceback

                traceback.print_exc()


if __name__ == "__main__":
    test_full_analytics_route()
