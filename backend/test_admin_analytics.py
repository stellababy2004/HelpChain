#!/usr/bin/env python
"""
Test script for admin analytics functionality
"""

import os
import sys
import tempfile

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

from appy import app
from backend.models import AdminUser


def test_admin_analytics():
    """Test admin analytics functionality"""

    # Create temporary database for testing
    db_fd, db_path = tempfile.mkstemp()

    try:
        app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False

        with app.app_context():
            # Import and initialize db
            from backend.extensions import db

            db.create_all()

            # Check if admin user exists, if not create it
            admin = AdminUser.query.filter_by(username="admin").first()
            if not admin:
                admin = AdminUser(username="admin", email="admin@helpchain.live")
                admin.set_password(os.getenv("ADMIN_PASSWORD", "test-password"))
                db.session.add(admin)
                db.session.commit()
                print("Admin user created successfully")
            else:
                print("Admin user already exists")

            # Test with app test client
            with app.test_client() as client:
                # Login
                response = client.post(
                    "/admin/login",
                    data={
                        "username": "admin",
                        "password": os.getenv("ADMIN_PASSWORD", "test-password"),
                    },
                    follow_redirects=True,
                )

                print(f"Login response status: {response.status_code}")

                # Check session
                with client.session_transaction() as sess:
                    print(f"Session admin_logged_in: {sess.get('admin_logged_in')}")

                # Try analytics
                response = client.get("/admin_analytics", follow_redirects=True)
                print(f"Analytics response status: {response.status_code}")

                if response.status_code == 200:
                    print("SUCCESS: Analytics page loaded!")
                    # Check if Chart.js data is present
                    data = response.get_data(as_text=True)
                    chart_elements = [
                        "trendsData",
                        "categoryStats",
                        "geoData",
                        "predictions",
                        "Chart.js",
                        "new Chart",
                        "trendsChart",
                        "categoryChart",
                    ]
                    found_elements = []
                    for element in chart_elements:
                        if element in data:
                            found_elements.append(element)
                        else:
                            print(f"WARNING: {element} not found in response")

                    if len(found_elements) >= 6:  # Most important elements
                        elements_str = ", ".join(found_elements)
                        print(f"SUCCESS: Chart.js data found! Found: {elements_str}")

                        # Check for specific chart data structures
                        if (
                            "trendsData" in data
                            and "labels" in data
                            and "requests" in data
                        ):
                            print("SUCCESS: Trends chart data structure is valid")
                        else:
                            print("WARNING: Trends chart data structure may be invalid")

                        if "categoryStats" in data:
                            print("SUCCESS: Category stats data found")
                        else:
                            print("WARNING: Category stats data not found")

                    else:
                        elements_str = ", ".join(found_elements)
                        print(
                            f"PARTIAL: Only found {len(found_elements)} chart elements: {elements_str}"
                        )
                        print("Response preview:", data[:1000])

                    # Verify the analytics blueprint respects custom date range filters
                    custom_response = client.get(
                        "/analytics/admin_analytics?start_date=2025-10-01&end_date=2025-10-07"
                    )
                    print(
                        f"Analytics blueprint (custom range) status: {custom_response.status_code}"
                    )
                    if custom_response.status_code == 200:
                        html = custom_response.get_data(as_text=True)
                        if "filterSummaryText" in html:
                            print("SUCCESS: Custom date range summary rendered")
                        else:
                            print("WARNING: Custom date range summary missing")
                        assert "01.10.2025" in html and "07.10.2025" in html
                    else:
                        print(
                            "FAILED: Blueprint analytics route with custom range did not load"
                        )
                        print(custom_response.get_data(as_text=True)[:500])
                else:
                    print("FAILED: Analytics page failed to load")
                    print("Response data:", response.get_data(as_text=True)[:1000])

    except Exception as e:
        print(f"Error during test: {e}")
        import traceback

        traceback.print_exc()

    finally:
        # Attempt to close and dispose DB resources before deleting the
        # temporary database file. On Windows unlinking an open SQLite
        # connection will fail, so remove sessions and dispose the engine
        # as a best-effort guard.
        try:
            from backend.extensions import db as _db

            try:
                with app.app_context():
                    try:
                        _db.session.remove()
                    except Exception:
                        pass
                    try:
                        _db.engine.dispose()
                    except Exception:
                        pass
            except Exception:
                # If app_context can't be entered for some reason, still
                # attempt module-level cleanup where possible.
                try:
                    _db.session.remove()
                except Exception:
                    pass
                try:
                    _db.engine.dispose()
                except Exception:
                    pass
        except Exception:
            pass

        # Clean up filesystem artifacts
        try:
            os.close(db_fd)
        except Exception:
            pass
        try:
            os.unlink(db_path)
        except Exception:
            pass


if __name__ == "__main__":
    test_admin_analytics()

