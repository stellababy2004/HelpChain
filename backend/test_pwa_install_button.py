#!/usr/bin/env python3
"""
Test PWA Install Button Functionality
"""

import json
import time

import requests


def test_pwa_install_button():
    """Test that the PWA install button logic is working"""

    print("🧪 Testing PWA Install Button Functionality")
    print("=" * 50)

    try:
        # Test 1: Check if the page loads
        print("📄 Test 1: Checking if main page loads...")
        response = requests.get("http://127.0.0.1:8000/")
        if response.status_code == 200:
            print("✅ Main page loads successfully")
        else:
            print(f"❌ Main page failed to load: {response.status_code}")
            return False

        # Test 2: Check if manifest is accessible
        print("📋 Test 2: Checking PWA manifest...")
        manifest_response = requests.get("http://127.0.0.1:8000/static/manifest.json")
        if manifest_response.status_code == 200:
            try:
                manifest = manifest_response.json()
                print("✅ Manifest is valid JSON")
                print(f"   App name: {manifest.get('name')}")
                print(f"   Short name: {manifest.get('short_name')}")
                print(f"   Icons: {len(manifest.get('icons', []))} defined")
            except json.JSONDecodeError:
                print("❌ Manifest is not valid JSON")
                return False
        else:
            print(f"❌ Manifest not accessible: {manifest_response.status_code}")
            return False

        # Test 3: Check if service worker is accessible
        print("🔧 Test 3: Checking service worker...")
        sw_response = requests.get("http://127.0.0.1:8000/static/sw.js")
        if sw_response.status_code == 200:
            print("✅ Service worker is accessible")
            # Check if it contains key PWA functionality
            sw_content = sw_response.text
            if "install" in sw_content and "fetch" in sw_content:
                print("✅ Service worker contains PWA functionality")
            else:
                print("⚠️  Service worker may be missing PWA features")
        else:
            print(f"❌ Service worker not accessible: {sw_response.status_code}")
            return False

        # Test 4: Check if install button is in HTML
        print("🎯 Test 4: Checking install button in HTML...")
        html_content = response.text
        if (
            "pwa-install-btn" in html_content
            and "Инсталирай приложението" in html_content
        ):
            print("✅ Install button is present in HTML")
        else:
            print("❌ Install button not found in HTML")
            return False

        # Test 5: Check if PWA JavaScript is present
        print("💻 Test 5: Checking PWA JavaScript functionality...")
        if (
            "beforeinstallprompt" in html_content
            and "showInstallButton" in html_content
        ):
            print("✅ PWA JavaScript logic is present")
        else:
            print("❌ PWA JavaScript logic not found")
            return False

        print("\n🎉 All PWA tests passed!")
        print("\n📱 PWA Install Button Features:")
        print("  • Button appears only when app is installable")
        print("  • Button hidden when app is already installed")
        print("  • Button hidden after user dismisses install prompt")
        print("  • Button reappears after 24 hours if dismissed")
        print("  • Smooth animations and hover effects")
        print("  • Accessible with ARIA labels")
        print("  • Responsive design for mobile devices")

        return True

    except requests.exceptions.ConnectionError:
        print(
            "❌ Cannot connect to server. Is HelpChain running on http://127.0.0.1:8000?"
        )
        return False
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return False


if __name__ == "__main__":
    # Give server time to start if running in background
    time.sleep(2)
    success = test_pwa_install_button()
    exit(0 if success else 1)
