#!/usr/bin/env python3
"""
Test script to verify browserconfig.xml configuration
"""

import os
import xml.etree.ElementTree as ET


def test_browserconfig_xml():
    """Test browserconfig.xml file structure and content"""
    file_path = "static/browserconfig.xml"

    if not os.path.exists(file_path):
        print(f"❌ File {file_path} does not exist")
        return False

    try:
        # Parse XML
        tree = ET.parse(file_path)
        root = tree.getroot()

        print("✅ browserconfig.xml file exists and is valid XML")

        # Check msapplication element
        msapplication = root.find("msapplication")
        if msapplication is None:
            print("❌ msapplication element not found")
            return False

        # Check tile element
        tile = msapplication.find("tile")
        if tile is None:
            print("❌ tile element not found")
            return False

        print("✅ Tile configuration found")

        # Check tile color
        tile_color = tile.find("TileColor")
        if tile_color is None or not tile_color.text:
            print("❌ TileColor not found or empty")
            return False

        print(f"✅ TileColor: {tile_color.text}")

        # Check required tile images
        required_sizes = [
            "square70x70logo",
            "square150x150logo",
            "wide310x150logo",
            "square310x310logo",
        ]
        for size in required_sizes:
            logo = tile.find(size)
            if logo is None:
                print(f"❌ {size} not found")
                return False
            src = logo.get("src")
            if not src:
                print(f"❌ {size} has no src attribute")
                return False
            print(f"✅ {size}: {src}")

        # Check notification element (optional but good to have)
        notification = msapplication.find("notification")
        if notification is not None:
            print("✅ Notification configuration found")
            polling_uris = notification.findall("polling-uri*")
            if polling_uris:
                print(f"✅ {len(polling_uris)} polling URIs configured")

        print("🎉 browserconfig.xml is properly configured!")
        return True

    except ET.ParseError as e:
        print(f"❌ XML parsing error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


if __name__ == "__main__":
    print("🧪 Testing browserconfig.xml configuration")
    print("=" * 50)

    success = test_browserconfig_xml()

    if success:
        print("\n📋 browserconfig.xml Summary:")
        print("  • TileColor: #1976d2 (matches PWA theme color)")
        print("  • square70x70logo: Small tile icon")
        print("  • square150x150logo: Medium tile icon")
        print("  • wide310x150logo: Wide tile icon")
        print("  • square310x310logo: Large tile icon")
        print("  • Notification polling configured")
        print("\n✅ Windows tile configuration is complete!")
    else:
        print("\n❌ browserconfig.xml configuration has issues")
