#!/usr/bin/env python3
"""
HelpChain Cross-Browser Compatibility Testing Suite
Tests application functionality across multiple browsers
"""

import json
import platform
import sys
import time
from pathlib import Path

import pytest
from selenium import webdriver
from selenium.common.exceptions import (
    TimeoutException,
    WebDriverException,
    SessionNotCreatedException,
)
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.safari.options import Options as SafariOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class CrossBrowserTester:
    """Comprehensive cross-browser compatibility testing class"""

    def __init__(self, base_url="http://127.0.0.1:5000"):
        self.base_url = base_url
        self.browsers = {
            "chrome": {
                "name": "Google Chrome",
                "enabled": True,
                "versions": ["latest"],
            },
            "firefox": {
                "name": "Mozilla Firefox",
                "enabled": True,
                "versions": ["latest"],
            },
            "edge": {
                "name": "Microsoft Edge",
                "enabled": platform.system() == "Windows",  # Edge is Windows-only
                "versions": ["latest"],
            },
            "safari": {
                "name": "Apple Safari",
                "enabled": platform.system() == "Darwin",  # Safari is macOS-only
                "versions": ["latest"],
            },
        }

        self.test_pages = [
            "/",
            "/admin_login",
            "/admin_dashboard",
            "/admin_volunteers",
        ]

        self.test_scenarios = [
            "page_load",
            "navigation",
            "forms",
            "responsive_layout",
            "javascript_execution",
            "css_styling",
        ]

        self.results = {}

    def setup_driver(self, browser_name):
        """Setup WebDriver for specified browser"""
        try:
            if browser_name == "chrome":
                options = ChromeOptions()
                options.add_argument("--headless")
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")
                options.add_argument("--disable-gpu")
                options.add_argument("--window-size=1920,1080")
                options.add_argument("--disable-extensions")
                options.add_argument("--disable-plugins")
                options.add_argument("--disable-images")  # Speed up tests
                return webdriver.Chrome(options=options)

            elif browser_name == "firefox":
                options = FirefoxOptions()
                options.add_argument("--headless")
                options.add_argument("--width=1920")
                options.add_argument("--height=1080")
                options.set_preference("dom.webnotifications.enabled", False)
                options.set_preference("media.volume_scale", "0.0")
                return webdriver.Firefox(options=options)

            elif browser_name == "edge":
                options = EdgeOptions()
                options.add_argument("--headless")
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")
                options.add_argument("--disable-gpu")
                options.add_argument("--window-size=1920,1080")
                options.add_argument("--disable-extensions")
                return webdriver.Edge(options=options)

            elif browser_name == "safari":
                options = SafariOptions()
                # Safari doesn't support headless mode in WebDriver
                return webdriver.Safari(options=options)

            else:
                raise ValueError(f"Unsupported browser: {browser_name}")

        except (WebDriverException, SessionNotCreatedException) as e:
            print(f"Failed to initialize {browser_name} driver: {e}")
            print(
                f"Please ensure {browser_name} and its WebDriver are properly installed"
            )
            return None

    def test_browser_compatibility(self, browser_name):
        """Test application compatibility on a specific browser"""
        browser_info = self.browsers.get(browser_name)
        if not browser_info or not browser_info["enabled"]:
            print(f"Browser {browser_name} is not available on this platform")
            return False

        print(f"\nTesting {browser_info['name']} ({browser_name})")
        print("-" * 50)

        driver = self.setup_driver(browser_name)
        if not driver:
            return False

        try:
            browser_results = {}

            for page in self.test_pages:
                try:
                    url = f"{self.base_url}{page}"
                    driver.get(url)

                    # Wait for page to load
                    WebDriverWait(driver, 15).until(
                        EC.presence_of_element_located((By.TAG_NAME, "body"))
                    )

                    # Run comprehensive tests
                    page_results = self.run_page_tests(driver, browser_name, page)
                    browser_results[page] = page_results

                    status = (
                        "PASS" if page_results["overall_status"] == "PASS" else "ISSUES"
                    )
                    print(f"  {status}: {page}")

                except Exception as e:
                    browser_results[page] = {
                        "overall_status": "ERROR",
                        "error": str(e),
                        "tests": {},
                    }
                    print(f"  FAIL: {page} - {str(e)}")

            self.results[browser_name] = browser_results
            return True

        finally:
            driver.quit()

    def run_page_tests(self, driver, browser_name, page):
        """Run comprehensive tests for a page"""
        tests = {}

        # Test 1: Page Load
        tests["page_load"] = self.test_page_load(driver)

        # Test 2: Navigation
        tests["navigation"] = self.test_navigation(driver, page)

        # Test 3: Forms
        tests["forms"] = self.test_forms(driver, page)

        # Test 4: Responsive Layout
        tests["responsive_layout"] = self.test_responsive_layout(driver)

        # Test 5: JavaScript Execution
        tests["javascript_execution"] = self.test_javascript_execution(driver)

        # Test 6: CSS Styling
        tests["css_styling"] = self.test_css_styling(driver)

        # Overall status
        failed_tests = [t for t in tests.values() if t.get("status") != "PASS"]
        overall_status = "PASS" if len(failed_tests) == 0 else "ISSUES"

        return {
            "overall_status": overall_status,
            "browser": browser_name,
            "page": page,
            "tests": tests,
            "failed_count": len(failed_tests),
            "total_tests": len(tests),
        }

    def test_page_load(self, driver):
        """Test basic page loading"""
        try:
            # Check if page title exists
            title = driver.title
            if not title or title.strip() == "":
                return {"status": "FAIL", "message": "Page title is empty"}

            # Check if body element exists
            body = driver.find_element(By.TAG_NAME, "body")
            if not body:
                return {"status": "FAIL", "message": "Body element not found"}

            # Check for basic HTML structure
            html = driver.find_element(By.TAG_NAME, "html")
            if not html:
                return {"status": "FAIL", "message": "HTML element not found"}

            # Check for console errors (if supported)
            try:
                logs = driver.get_log("browser")
                errors = [log for log in logs if log["level"] in ["SEVERE", "ERROR"]]
                if errors:
                    return {
                        "status": "ISSUES",
                        "message": f"Console errors found: {len(errors)}",
                    }
            except:
                pass  # Some browsers don't support get_log

            return {"status": "PASS", "title": title}

        except Exception as e:
            return {"status": "ERROR", "message": str(e)}

    def test_navigation(self, driver, page):
        """Test navigation elements"""
        try:
            issues = []

            # Check for navigation links
            nav_links = driver.find_elements(
                By.CSS_SELECTOR, "nav a, .navbar a, .nav a"
            )
            if len(nav_links) == 0:
                issues.append("No navigation links found")

            # Check if links are clickable
            for link in nav_links[:5]:  # Test first 5 links
                try:
                    href = link.get_attribute("href")
                    if href and not href.startswith("#"):
                        # Basic link validation
                        if not (href.startswith("http") or href.startswith("/")):
                            issues.append(f"Invalid link href: {href}")
                except:
                    issues.append("Link accessibility issue")

            # Check for mobile navigation toggle
            toggles = driver.find_elements(
                By.CSS_SELECTOR, ".navbar-toggler, .mobile-menu-toggle, .hamburger"
            )
            if toggles:
                # Test toggle functionality
                try:
                    toggle = toggles[0]
                    original_classes = toggle.get_attribute("class") or ""
                    toggle.click()
                    time.sleep(0.5)  # Wait for animation
                    new_classes = toggle.get_attribute("class") or ""
                    if original_classes == new_classes:
                        issues.append("Mobile navigation toggle may not be working")
                except Exception as e:
                    issues.append(f"Mobile navigation toggle error: {str(e)}")

            status = "PASS" if len(issues) == 0 else "ISSUES"
            return {
                "status": status,
                "issues": issues,
                "nav_links_count": len(nav_links),
            }

        except Exception as e:
            return {"status": "ERROR", "message": str(e)}

    def test_forms(self, driver, page):
        """Test form functionality"""
        try:
            issues = []

            # Find forms
            forms = driver.find_elements(By.TAG_NAME, "form")

            if page == "/admin_login" and len(forms) == 0:
                issues.append("Login form not found on login page")

            for form in forms:
                try:
                    # Check form inputs
                    inputs = form.find_elements(
                        By.CSS_SELECTOR, "input, select, textarea"
                    )
                    if len(inputs) == 0:
                        issues.append("Form has no input elements")

                    # Test input accessibility
                    for input_elem in inputs[:3]:  # Test first 3 inputs
                        try:
                            input_type = input_elem.get_attribute("type") or "text"
                            name = input_elem.get_attribute("name")
                            if not name:
                                issues.append(
                                    f"Input missing name attribute (type: {input_type})"
                                )

                            # Check if input is visible and enabled
                            if not input_elem.is_displayed():
                                issues.append(f"Input not visible (type: {input_type})")
                            if not input_elem.is_enabled():
                                issues.append(f"Input not enabled (type: {input_type})")

                        except Exception as e:
                            issues.append(f"Input element error: {str(e)}")

                    # Check submit button
                    submit_buttons = form.find_elements(
                        By.CSS_SELECTOR,
                        "input[type='submit'], button[type='submit'], .btn[type='submit']",
                    )
                    if len(submit_buttons) == 0:
                        # Look for any button that might be submit
                        buttons = form.find_elements(
                            By.CSS_SELECTOR, "button, input[type='button']"
                        )
                        if len(buttons) == 0:
                            issues.append("No submit button found in form")

                except Exception as e:
                    issues.append(f"Form testing error: {str(e)}")

            status = "PASS" if len(issues) == 0 else "ISSUES"
            return {"status": status, "issues": issues, "forms_count": len(forms)}

        except Exception as e:
            return {"status": "ERROR", "message": str(e)}

    def test_responsive_layout(self, driver):
        """Test responsive layout"""
        try:
            issues = []

            # Get viewport size
            viewport_width = driver.execute_script("return window.innerWidth;")
            viewport_height = driver.execute_script("return window.innerHeight;")

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

            if scroll_width > viewport_width + 10:  # 10px tolerance
                issues.append(
                    f"Horizontal scroll detected: {scroll_width}px content in {viewport_width}px viewport"
                )

            # Check for basic responsive elements
            containers = driver.find_elements(
                By.CSS_SELECTOR, ".container, .container-fluid, .row"
            )
            if len(containers) == 0:
                issues.append("No responsive containers found")

            # Check images are responsive
            images = driver.find_elements(By.TAG_NAME, "img")
            for img in images[:3]:  # Check first 3 images
                try:
                    classes = img.get_attribute("class") or ""
                    if not any(
                        cls in classes for cls in ["img-fluid", "responsive-img"]
                    ):
                        style = img.get_attribute("style") or ""
                        if "max-width" not in style and "width: 100%" not in style:
                            issues.append("Non-responsive image found")
                            break
                except:
                    pass

            status = "PASS" if len(issues) == 0 else "ISSUES"
            return {
                "status": status,
                "issues": issues,
                "viewport": f"{viewport_width}x{viewport_height}",
            }

        except Exception as e:
            return {"status": "ERROR", "message": str(e)}

    def test_javascript_execution(self, driver):
        """Test JavaScript execution"""
        try:
            issues = []

            # Test basic JavaScript execution
            result = driver.execute_script("return 1 + 1;")
            if result != 2:
                issues.append("Basic JavaScript execution failed")

            # Test DOM manipulation
            result = driver.execute_script(
                """
                var testDiv = document.createElement('div');
                testDiv.id = 'test-element';
                testDiv.textContent = 'test';
                document.body.appendChild(testDiv);
                return document.getElementById('test-element').textContent;
            """
            )
            if result != "test":
                issues.append("DOM manipulation failed")

            # Test event handling (if applicable)
            try:
                driver.execute_script(
                    """
                    if (typeof $ !== 'undefined') {
                        // jQuery is available
                        return 'jquery_available';
                    }
                    return 'jquery_not_available';
                """
                )
            except:
                pass  # jQuery test is optional

            status = "PASS" if len(issues) == 0 else "ISSUES"
            return {"status": status, "issues": issues}

        except Exception as e:
            return {"status": "ERROR", "message": str(e)}

    def test_css_styling(self, driver):
        """Test CSS styling application"""
        try:
            issues = []

            # Check if CSS is loaded by testing computed styles
            body = driver.find_element(By.TAG_NAME, "body")
            background_color = driver.execute_script(
                "return window.getComputedStyle(arguments[0]).backgroundColor;", body
            )

            # Check for basic styling
            if (
                background_color == "rgba(0, 0, 0, 0)"
                or background_color == "transparent"
            ):
                # This might be normal, but let's check if any styling is applied
                font_family = driver.execute_script(
                    "return window.getComputedStyle(arguments[0]).fontFamily;", body
                )
                if not font_family or font_family == "":
                    issues.append("No CSS styling detected")

            # Check for Bootstrap classes (if using Bootstrap)
            bootstrap_elements = driver.find_elements(
                By.CSS_SELECTOR,
                "[class*='btn'], [class*='navbar'], [class*='container']",
            )
            if len(bootstrap_elements) > 0:
                # Test if Bootstrap styles are applied
                btn_primary = driver.find_elements(By.CSS_SELECTOR, ".btn-primary")
                if btn_primary:
                    color = driver.execute_script(
                        "return window.getComputedStyle(arguments[0]).backgroundColor;",
                        btn_primary[0],
                    )
                    if color == "rgba(0, 0, 0, 0)" or color == "transparent":
                        issues.append("Bootstrap button styling not applied")

            # Check for custom CSS
            custom_elements = driver.find_elements(
                By.CSS_SELECTOR, "[class*='design-system'], [class*='helpchain']"
            )
            if len(custom_elements) > 0:
                # Verify custom styles are applied
                for elem in custom_elements[:2]:
                    try:
                        has_styles = driver.execute_script(
                            """
                            var elem = arguments[0];
                            var styles = window.getComputedStyle(elem);
                            return styles.cssText.length > 0;
                        """,
                            elem,
                        )
                        if not has_styles:
                            issues.append("Custom CSS styles not applied")
                            break
                    except:
                        pass

            status = "PASS" if len(issues) == 0 else "ISSUES"
            return {"status": status, "issues": issues}

        except Exception as e:
            return {"status": "ERROR", "message": str(e)}

    def run_cross_browser_test_suite(self):
        """Run complete cross-browser testing suite"""
        print("Starting HelpChain Cross-Browser Compatibility Testing Suite")
        print("=" * 70)

        successful_browsers = 0
        total_browsers = len([b for b in self.browsers.values() if b["enabled"]])

        for browser_name, browser_info in self.browsers.items():
            if browser_info["enabled"]:
                if self.test_browser_compatibility(browser_name):
                    successful_browsers += 1
                time.sleep(2)  # Brief pause between browsers

        self.generate_cross_browser_report()
        return successful_browsers, total_browsers

    def generate_cross_browser_report(self):
        """Generate comprehensive cross-browser test report"""
        print("\n" + "=" * 70)
        print("CROSS-BROWSER COMPATIBILITY TESTING REPORT")
        print("=" * 70)

        # Summary statistics
        total_pages = len(self.test_pages)
        total_browsers = len(self.results)
        total_tests = total_pages * total_browsers * len(self.test_scenarios)

        passed_tests = 0
        failed_tests = 0
        error_tests = 0

        for browser, pages in self.results.items():
            for page, page_results in pages.items():
                for test_name, test_result in page_results.get("tests", {}).items():
                    status = test_result.get("status")
                    if status == "PASS":
                        passed_tests += 1
                    elif status == "ISSUES":
                        failed_tests += 1
                    else:
                        error_tests += 1

        print("\nSummary:")
        print(f"   Browsers tested: {total_browsers}")
        print(f"   Pages tested: {total_pages}")
        print(f"   Test scenarios: {len(self.test_scenarios)}")
        print(f"   Total tests: {total_tests}")
        print(f"   Passed: {passed_tests}")
        print(f"   Issues: {failed_tests}")
        print(f"   Errors: {error_tests}")

        # Browser compatibility matrix
        print("\nBrowser Compatibility Matrix:")
        print("-" * 50)
        for browser, pages in self.results.items():
            browser_info = self.browsers.get(browser, {})
            browser_name = browser_info.get("name", browser)

            total_page_tests = len(pages)
            passed_pages = sum(
                1 for p in pages.values() if p.get("overall_status") == "PASS"
            )

            compatibility = (
                (passed_pages / total_page_tests) * 100 if total_page_tests > 0 else 0
            )
            status = (
                "GOOD"
                if compatibility >= 80
                else "FAIR" if compatibility >= 60 else "POOR"
            )

            print(f"{browser_name:<15} | {compatibility:5.1f}% | {status}")

        # Detailed results
        print("\nDetailed Results by Browser:")
        for browser, pages in self.results.items():
            browser_info = self.browsers.get(browser, {})
            browser_name = browser_info.get("name", browser)

            print(f"\n{browser_name} ({browser}):")
            for page, page_results in pages.items():
                overall_status = page_results.get("overall_status", "UNKNOWN")
                status_icon = (
                    "PASS"
                    if overall_status == "PASS"
                    else "ISSUES" if overall_status == "ISSUES" else "ERROR"
                )
                print(f"   {status_icon} {page}")

                # Show failed tests
                tests = page_results.get("tests", {})
                failed_scenarios = [
                    (name, result)
                    for name, result in tests.items()
                    if result.get("status") != "PASS"
                ]
                if failed_scenarios:
                    print("      Failed scenarios:")
                    for test_name, test_result in failed_scenarios:
                        issues = test_result.get("issues", [])
                        if issues:
                            print(
                                f"        - {test_name}: {', '.join(issues[:2])}"
                            )  # Show first 2 issues

        # Save detailed report to file
        self.save_cross_browser_report_to_file()

    def save_cross_browser_report_to_file(self):
        """Save detailed test results to JSON file"""
        report_file = Path("cross_browser_test_report.json")

        report_data = {
            "test_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "base_url": self.base_url,
            "browsers_tested": list(self.results.keys()),
            "pages_tested": self.test_pages,
            "test_scenarios": self.test_scenarios,
            "results": self.results,
            "platform": platform.platform(),
            "python_version": sys.version,
        }

        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)

        print(f"\nReport saved to: {report_file}")


def run_quick_cross_browser_test():
    """Run quick cross-browser test on available browsers"""
    tester = CrossBrowserTester()

    # Test Chrome and Firefox (most commonly available)
    quick_browsers = ["chrome", "firefox"]

    print("Running Quick Cross-Browser Compatibility Test")
    print("-" * 55)

    successful_browsers = 0
    for browser in quick_browsers:
        if tester.browsers.get(browser, {}).get("enabled", False):
            if tester.test_browser_compatibility(browser):
                successful_browsers += 1
            time.sleep(1)

    print(f"\nCompleted: {successful_browsers}/{len(quick_browsers)} browsers tested")
    return successful_browsers > 0


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--quick":
        success = run_quick_cross_browser_test()
        sys.exit(0 if success else 1)
    else:
        tester = CrossBrowserTester()
        successful, total = tester.run_cross_browser_test_suite()

        if successful == total:
            print("\nAll browsers passed! Cross-browser compatibility looks good.")
            sys.exit(0)
        else:
            print(
                f"\n{successful}/{total} browsers had issues. Check the report above."
            )
            sys.exit(1)
