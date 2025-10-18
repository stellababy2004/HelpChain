#!/usr/bin/env python3
"""
Test script to verify PWA install button functionality
"""

import requests
import time
from bs4 import BeautifulSoup


def test_pwa_manifest():
    """Test if PWA manifest is accessible"""
    try:
        response = requests.get("http://localhost:5000/manifest.json", timeout=5)
        if response.status_code == 200:
            manifest = response.json()
            required_fields = ["name", "short_name", "start_url", "display", "icons"]
            for field in required_fields:
                if field not in manifest:
                    print(f"❌ Manifest missing required field: {field}")
                    return False
            print("✅ PWA manifest is valid")
            return True
        else:
            print(f"❌ Manifest not accessible (status: {response.status_code})")
            return False
    except Exception as e:
        print(f"❌ Error checking manifest: {e}")
        return False


def test_service_worker():
    """Test if service worker is accessible"""
    try:
        response = requests.get("http://localhost:5000/sw.js", timeout=5)
        if response.status_code == 200:
            print("✅ Service worker is accessible")
            return True
        else:
            print(f"❌ Service worker not accessible (status: {response.status_code})")
            return False
    except Exception as e:
        print(f"❌ Error checking service worker: {e}")
        return False


def test_install_button_in_html():
    """Test if install button is present in the HTML"""
    try:
        response = requests.get("http://localhost:5000/", timeout=5)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")

            # Check for install button
            install_button = soup.find(id="pwa-install-btn")
            if install_button:
                print("✅ Install button found in HTML")
                return True
            else:
                print("❌ Install button not found in HTML")
                return False
        else:
            print(f"❌ Homepage not accessible (status: {response.status_code})")
            return False
    except Exception as e:
        print(f"❌ Error checking HTML: {e}")
        return False


def test_pwa_meta_tags():
    """Test if PWA meta tags are present"""
    try:
        response = requests.get("http://localhost:5000/", timeout=5)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")

            # Check for manifest link
            manifest_link = soup.find("link", {"rel": "manifest"})
            if not manifest_link:
                print("❌ Manifest link not found in HTML")
                return False

            # Check for theme-color meta tag
            theme_color = soup.find("meta", {"name": "theme-color"})
            if not theme_color:
                print("❌ Theme-color meta tag not found")
                return False

            print("✅ PWA meta tags are present")
            return True
        else:
            print(f"❌ Homepage not accessible (status: {response.status_code})")
            return False
    except Exception as e:
        print(f"❌ Error checking meta tags: {e}")
        return False


def wait_for_server(max_wait=30):
    """Wait for server to be ready"""
    start_time = time.time()
    while time.time() - start_time < max_wait:
        try:
            response = requests.get("http://localhost:5000/", timeout=2)
            if response.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def main():
    print("🧪 Testing PWA Install Button Implementation")
    print("=" * 50)

    # Wait for server to be ready
    print("⏳ Waiting for server to be ready...")
    if not wait_for_server():
        print("❌ Server not ready after 30 seconds")
        return

    print("✅ Server is ready")

    # Run tests
    tests = [
        test_pwa_manifest,
        test_service_worker,
        test_pwa_meta_tags,
        test_install_button_in_html,
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")

    print("=" * 50)
    print(f"📊 Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All PWA install button tests passed!")
    else:
        print("⚠️  Some tests failed. Check the output above.")


if __name__ == "__main__":
    main()
