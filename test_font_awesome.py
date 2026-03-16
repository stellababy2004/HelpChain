#!/usr/bin/env python3
"""
Simple Font Awesome Test for HelpChain
"""

import os
import sys
from pathlib import Path


def test_font_awesome():
    """Test Font Awesome integration"""
    print("Testing Font Awesome integration...")

    # Check base.html
    base_html = Path("backend/templates/base.html")
    if not base_html.exists():
        print("❌ base.html not found")
        return False

    with open(base_html, encoding="utf-8") as f:
        content = f.read()

    if "cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css" in content:
        print("✅ Font Awesome CSS found in base.html")
    else:
        print("❌ Font Awesome CSS NOT found in base.html")
        return False

    # Check admin dashboard
    admin_html = Path("backend/templates/admin_dashboard.html")
    if admin_html.exists():
        with open(admin_html, encoding="utf-8") as f:
            content = f.read()

        if "fas fa-shield-alt" in content and "fas fa-users" in content:
            print("✅ Font Awesome classes found in admin_dashboard.html")
        else:
            print("❌ Font Awesome classes NOT found in admin_dashboard.html")
            return False

    # Check dashboard nav
    nav_html = Path("backend/templates/dashboard_nav.html")
    if nav_html.exists():
        with open(nav_html, encoding="utf-8") as f:
            content = f.read()

        if "fas fa-tachometer-alt" in content and "fas fa-users" in content:
            print("✅ Font Awesome classes found in dashboard_nav.html")
        else:
            print("❌ Font Awesome classes NOT found in dashboard_nav.html")
            return False

    print("✅ All Font Awesome tests passed!")
    return True


def test_app_import():
    """Test Flask app import"""
    print("Testing Flask app import...")

    try:
        sys.path.insert(0, "backend")
        from appy import app

        print("✅ Flask app imported successfully")

        with app.app_context():
            print("✅ Flask app context created")
            return True
    except Exception as e:
        print(f"❌ App import failed: {e}")
        return False


if __name__ == "__main__":
    print("🚀 HelpChain Font Awesome Test")
    print("=" * 40)

    fa_test = test_font_awesome()
    app_test = test_app_import()

    print("\n" + "=" * 40)
    if fa_test and app_test:
        print("🎉 SUCCESS: Font Awesome is properly integrated!")
        print("\nTo test the admin dashboard:")
        print("1. Start server: python run.py")
        print("2. Visit: http://localhost:8000/admin/login")
        print("3. Login with: admin / test-password")
        print("4. Check that all icons are visible in the navigation and buttons")
    else:
        print("❌ FAILED: Issues found with Font Awesome integration")

