#!/usr/bin/env python3
"""
HelpChain Mobile Responsive Testing Suite
Tests responsive design across multiple screen sizes and devices
"""

import json
import sys
import time
from pathlib import Path

import pytest
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class MobileResponsiveTester:
    """Comprehensive mobile responsive testing class"""

    def __init__(self, base_url="http://127.0.0.1:5000"):
        self.base_url = base_url
        self.devices = {
            # Mobile devices
            "iPhone_SE": {"width": 375, "height": 667, "deviceScaleFactor": 2},
            "iPhone_12": {"width": 390, "height": 844, "deviceScaleFactor": 3},
            "iPhone_12_Pro_Max": {"width": 428, "height": 926, "deviceScaleFactor": 3},
            "Samsung_Galaxy_S20": {
                "width": 412,
                "height": 915,
                "deviceScaleFactor": 3.5,
            },
            "Pixel_5": {"width": 393, "height": 851, "deviceScaleFactor": 2.75},
            # Tablets
            "iPad": {"width": 768, "height": 1024, "deviceScaleFactor": 2},
            "iPad_Pro": {"width": 1024, "height": 1366, "deviceScaleFactor": 2},
            "Samsung_Galaxy_Tab_S7": {
                "width": 800,
                "height": 1280,
                "deviceScaleFactor": 2,
            },
            # Desktop breakpoints
            "Desktop_Small": {"width": 1024, "height": 768, "deviceScaleFactor": 1},
            "Desktop_Medium": {"width": 1280, "height": 720, "deviceScaleFactor": 1},
            "Desktop_Large": {"width": 1920, "height": 1080, "deviceScaleFactor": 1},
        }

        self.test_pages = [
            "/",
            "/admin_login",
            "/admin_dashboard",
            "/admin_volunteers",
        ]

        self.results = {}

    def setup_driver(self):
        """Setup Chrome driver with mobile emulation"""
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Run in headless mode
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")

        try:
            driver = webdriver.Chrome(options=chrome_options)
            return driver
        except WebDriverException as e:
            print(f"Failed to initialize Chrome driver: {e}")
            print("Please ensure ChromeDriver is installed and in PATH")
            return None

    def test_device_responsiveness(self, device_name, device_config):
        """Test a specific device/screen size"""
        print(
            f"\nTesting {device_name} ({device_config['width']}x{device_config['height']})"
        )

        driver = self.setup_driver()
        if not driver:
            return False

        try:
            # Set viewport size
            driver.set_window_size(device_config["width"], device_config["height"])

            device_results = {}

            for page in self.test_pages:
                try:
                    url = f"{self.base_url}{page}"
                    driver.get(url)

                    # Wait for page to load
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.TAG_NAME, "body"))
                    )

                    # Get page metrics
                    page_results = self.analyze_page_responsiveness(
                        driver, device_name, page
                    )
                    device_results[page] = page_results

                    print(f"  PASS: {page}: {page_results['status']}")

                except Exception as e:
                    device_results[page] = {
                        "status": "ERROR",
                        "error": str(e),
                        "width": device_config["width"],
                        "height": device_config["height"],
                    }
                    print(f"  FAIL: {page}: ERROR - {str(e)}")

            self.results[device_name] = device_results
            return True

        finally:
            driver.quit()

    def analyze_page_responsiveness(self, driver, device_name, page):
        """Analyze page responsiveness for a specific device"""
        try:
            # Get viewport dimensions
            viewport_width = driver.execute_script("return window.innerWidth;")
            viewport_height = driver.execute_script("return window.innerHeight;")

            # Check for mobile navigation (hamburger menu)
            mobile_nav = self.check_mobile_navigation(driver)

            # Check for horizontal scroll
            scroll_width = driver.execute_script(
                """
                return Math.max(
                    document.body.scrollWidth,
                    document.body.offsetWidth,
                    document.documentElement.clientWidth,
                    document.documentElement.scrollWidth,
                    document.documentElement.offsetWidth
                );
            """
            )

            has_horizontal_scroll = scroll_width > viewport_width + 10  # 10px tolerance

            # Check touch targets
            touch_targets_ok = self.check_touch_targets(driver, device_name)

            # Check text readability
            text_readable = self.check_text_readability(driver)

            # Check images responsiveness
            images_responsive = self.check_images_responsive(driver)

            # Overall status
            issues = []
            if has_horizontal_scroll:
                issues.append("Horizontal scroll detected")
            if not touch_targets_ok:
                issues.append("Touch targets too small")
            if not text_readable:
                issues.append("Text may be too small")
            if not images_responsive:
                issues.append("Images not responsive")

            status = "PASS" if len(issues) == 0 else "ISSUES"

            return {
                "status": status,
                "viewport_width": viewport_width,
                "viewport_height": viewport_height,
                "has_horizontal_scroll": has_horizontal_scroll,
                "mobile_nav_detected": mobile_nav,
                "touch_targets_ok": touch_targets_ok,
                "text_readable": text_readable,
                "images_responsive": images_responsive,
                "issues": issues,
                "device_width": driver.get_window_size()["width"],
                "device_height": driver.get_window_size()["height"],
            }

        except Exception as e:
            return {"status": "ERROR", "error": str(e)}

    def check_mobile_navigation(self, driver):
        """Check if mobile navigation is present and working"""
        try:
            # Look for common mobile nav patterns
            mobile_nav_selectors = [
                ".navbar-toggler",
                ".mobile-menu-toggle",
                ".hamburger",
                "[data-toggle='collapse']",
                ".nav-toggle",
            ]

            for selector in mobile_nav_selectors:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    return True

            # Check if navbar collapses on small screens
            navbar = driver.find_elements(By.CSS_SELECTOR, ".navbar-collapse")
            if navbar:
                # Check if navbar is collapsed
                is_collapsed = driver.execute_script(
                    """
                    var navbar = document.querySelector('.navbar-collapse');
                    return navbar && (navbar.classList.contains('collapse') ||
                           window.getComputedStyle(navbar).display === 'none');
                """
                )
                return is_collapsed

            return False

        except Exception:
            return False

    def check_touch_targets(self, driver, device_name):
        """Check if interactive elements meet touch target requirements"""
        try:
            # Minimum touch target size (44px as per WCAG)
            min_touch_size = 44

            # Check buttons, links, and form inputs
            interactive_selectors = [
                "button",
                "a",
                "input[type='submit']",
                "input[type='button']",
                ".btn",
                "[role='button']",
                "[onclick]",
            ]

            all_targets_ok = True

            for selector in interactive_selectors:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)

                for element in elements:
                    try:
                        rect = element.rect
                        width = rect["width"]
                        height = rect["height"]

                        # Check if element meets minimum size
                        if width < min_touch_size or height < min_touch_size:
                            # Allow smaller elements if they have adequate padding
                            computed_style = driver.execute_script(
                                """
                                var elem = arguments[0];
                                var style = window.getComputedStyle(elem);
                                return {
                                    paddingTop: parseFloat(style.paddingTop),
                                    paddingBottom: parseFloat(style.paddingBottom),
                                    paddingLeft: parseFloat(style.paddingLeft),
                                    paddingRight: parseFloat(style.paddingRight)
                                };
                            """,
                                element,
                            )

                            effective_width = (
                                width
                                + computed_style["paddingLeft"]
                                + computed_style["paddingRight"]
                            )
                            effective_height = (
                                height
                                + computed_style["paddingTop"]
                                + computed_style["paddingBottom"]
                            )

                            if (
                                effective_width < min_touch_size
                                or effective_height < min_touch_size
                            ):
                                all_targets_ok = False
                                break

                    except Exception:
                        continue

                if not all_targets_ok:
                    break

            return all_targets_ok

        except Exception:
            return False

    def check_text_readability(self, driver):
        """Check if text is readable on the device"""
        try:
            # Check font sizes
            text_elements = driver.find_elements(
                By.CSS_SELECTOR, "p, h1, h2, h3, h4, h5, h6, span, div"
            )

            min_font_size = 14  # Minimum readable font size in pixels
            readable_text = True

            for element in text_elements[:10]:  # Check first 10 text elements
                try:
                    font_size = driver.execute_script(
                        """
                        var elem = arguments[0];
                        return parseFloat(window.getComputedStyle(elem).fontSize);
                    """,
                        element,
                    )

                    if font_size < min_font_size and element.text.strip():
                        readable_text = False
                        break

                except Exception:
                    continue

            return readable_text

        except Exception:
            return False

    def check_images_responsive(self, driver):
        """Check if images are responsive"""
        try:
            images = driver.find_elements(By.TAG_NAME, "img")
            responsive_images = True

            for img in images:
                try:
                    # Check if image has responsive classes or max-width
                    classes = img.get_attribute("class") or ""
                    style = img.get_attribute("style") or ""

                    has_responsive_class = any(
                        cls in classes for cls in ["img-fluid", "responsive-img"]
                    )
                    has_max_width = "max-width" in style or "width: 100%" in style

                    if not (has_responsive_class or has_max_width):
                        # Check computed style
                        max_width = driver.execute_script(
                            """
                            var img = arguments[0];
                            return window.getComputedStyle(img).maxWidth;
                        """,
                            img,
                        )

                        if max_width not in ["100%", "none"]:
                            responsive_images = False
                            break

                except Exception:
                    continue

            return responsive_images

        except Exception:
            return False

    def run_full_test_suite(self):
        """Run complete responsive testing suite"""
        print("Starting HelpChain Mobile Responsive Testing Suite")
        print("=" * 60)

        successful_tests = 0
        total_tests = len(self.devices)

        for device_name, config in self.devices.items():
            if self.test_device_responsiveness(device_name, config):
                successful_tests += 1
            time.sleep(1)  # Brief pause between tests

        self.generate_report()
        return successful_tests, total_tests

    def generate_report(self):
        """Generate comprehensive test report"""
        print("\n" + "=" * 60)
        print("📊 MOBILE RESPONSIVE TESTING REPORT")
        print("=" * 60)

        # Summary statistics
        total_pages = len(self.test_pages)
        total_devices = len(self.devices)
        total_tests = total_pages * total_devices

        passed_tests = 0
        failed_tests = 0
        error_tests = 0

        for device, pages in self.results.items():
            for page, result in pages.items():
                if result.get("status") == "PASS":
                    passed_tests += 1
                elif result.get("status") == "ISSUES":
                    failed_tests += 1
                else:
                    error_tests += 1

        print(f"\nSummary:")
        print(f"   Devices tested: {total_devices}")
        print(f"   Pages tested: {total_pages}")
        print(f"   Total tests: {total_tests}")
        print(f"   Passed: {passed_tests}")
        print(f"   Issues: {failed_tests}")
        print(f"   Errors: {error_tests}")

        # Detailed results
        print("\nDetailed Results:")

        for device, pages in self.results.items():
            print(f"\nDevice: {device}:")
            for page, result in pages.items():
                status_icon = (
                    "PASS"
                    if result.get("status") == "PASS"
                    else "ISSUES" if result.get("status") == "ISSUES" else "ERROR"
                )
                print(f"   {status_icon} {page}: {result.get('status', 'UNKNOWN')}")

                if result.get("issues"):
                    for issue in result["issues"]:
                        print(f"      - {issue}")

        # Save detailed report to file
        self.save_report_to_file()

    def save_report_to_file(self):
        """Save detailed test results to JSON file"""
        report_file = Path("mobile_test_report.json")

        report_data = {
            "test_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "base_url": self.base_url,
            "devices_tested": list(self.devices.keys()),
            "pages_tested": self.test_pages,
            "results": self.results,
        }

        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)

        print(f"\nReport saved to: {report_file}")


def run_quick_test():
    """Run a quick test on a few key devices"""
    tester = MobileResponsiveTester()

    # Test only key devices for quick feedback
    quick_devices = ["iPhone_SE", "iPad", "Desktop_Small"]

    print("Running Quick Mobile Responsive Test")
    print("-" * 40)

    successful_tests = 0
    for device in quick_devices:
        if device in tester.devices:
            if tester.test_device_responsiveness(device, tester.devices[device]):
                successful_tests += 1

    print(f"\nCompleted: {successful_tests}/{len(quick_devices)} devices tested")
    return successful_tests == len(quick_devices)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--quick":
        success = run_quick_test()
        sys.exit(0 if success else 1)
    else:
        tester = MobileResponsiveTester()
        successful, total = tester.run_full_test_suite()

        if successful == total:
            print("\nAll tests passed! Mobile responsiveness looks good.")
            sys.exit(0)
        else:
            print(
                f"\n{total - successful} device(s) had issues. Check the report above."
            )
            sys.exit(1)
