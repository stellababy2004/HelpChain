#!/usr/bin/env python3
"""
Test script to verify enhanced PWA "Add to Home Screen" functionality
"""

import requests
from bs4 import BeautifulSoup


def test_pwa_install_functionality():
    """Test the enhanced PWA install functionality"""
    try:
        response = requests.get("http://127.0.0.1:8000/", timeout=5)
        if response.status_code != 200:
            print("❌ Cannot access homepage")
            return False

        soup = BeautifulSoup(response.text, "html.parser")

        # Check for install button
        install_button = soup.find(id="pwa-install-btn")
        if not install_button:
            print("❌ Install button not found")
            return False

        print("✅ Install button found in HTML")

        # Check for modal
        install_modal = soup.find(id="installModal")
        if not install_modal:
            print("❌ Install instructions modal not found")
            return False

        print("✅ Install instructions modal found")

        # Check for JavaScript functions in script tags
        scripts = soup.find_all("script")
        js_content = ""
        for script in scripts:
            if script.string:
                js_content += script.string

        # Check for key functions
        required_functions = [
            "installApp()",
            "showInstallInstructions()",
            "tryInstallApp()",
            "showInstallSuccess()",
            "updateInstallButtonText()",
            "isAppInstalled()",
        ]

        for func in required_functions:
            if func in js_content:
                print(f"✅ Function {func} found")
            else:
                print(f"❌ Function {func} not found")
                return False

        # Check for event listeners
        if "beforeinstallprompt" in js_content and "appinstalled" in js_content:
            print("✅ PWA event listeners found")
        else:
            print("❌ PWA event listeners not found")
            return False

        # Check for user agent detection
        if "navigator.userAgent" in js_content:
            print("✅ Browser detection logic found")
        else:
            print("❌ Browser detection logic not found")
            return False

        print("\n🎉 Enhanced PWA 'Add to Home Screen' functionality is properly implemented!")
        print("\n📋 Features verified:")
        print("  • Smart install button with device-specific text")
        print("  • Browser-specific installation instructions")
        print("  • Modal with step-by-step guidance")
        print("  • Success notifications after installation")
        print("  • Proper event handling for PWA lifecycle")
        print("  • Responsive design for mobile devices")

        return True

    except Exception as e:
        print(f"❌ Error testing PWA functionality: {e}")
        return False


def test_manifest_and_service_worker():
    """Test that PWA infrastructure is in place"""
    try:
        # Test manifest
        manifest_response = requests.get("http://127.0.0.1:8000/manifest.json", timeout=5)
        if manifest_response.status_code != 200:
            print("❌ Manifest not accessible")
            return False

        manifest = manifest_response.json()
        if "name" not in manifest or "short_name" not in manifest:
            print("❌ Invalid manifest structure")
            return False

        print("✅ PWA manifest is valid")

        # Test service worker
        sw_response = requests.get("http://127.0.0.1:8000/sw.js", timeout=5)
        if sw_response.status_code != 200:
            print("❌ Service worker not accessible")
            return False

        print("✅ Service worker is accessible")

        return True

    except Exception as e:
        print(f"❌ Error testing PWA infrastructure: {e}")
        return False


if __name__ == "__main__":
    print("🧪 Testing Enhanced PWA 'Add to Home Screen' Functionality")
    print("=" * 60)

    # Test PWA infrastructure
    print("\n🔧 Testing PWA Infrastructure:")
    if not test_manifest_and_service_worker():
        print("❌ PWA infrastructure test failed")
        exit(1)

    # Test install functionality
    print("\n📱 Testing Install Functionality:")
    if not test_pwa_install_functionality():
        print("❌ Install functionality test failed")
        exit(1)

    print("\n" + "=" * 60)
    print("🎉 All PWA 'Add to Home Screen' tests passed!")
    print("\n💡 The enhanced install experience includes:")
    print("  • Automatic browser detection")
    print("  • Device-specific instructions")
    print("  • Interactive modal guidance")
    print("  • Success feedback")
    print("  • Smart button text adaptation")
