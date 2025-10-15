#!/usr/bin/env python3
"""
Comprehensive integration test for HelpChain application
Tests all major functionality: admin login, analytics, AI chatbot, volunteers, help requests, emails, gamification
"""

import requests
import time
import sys
import os
from datetime import datetime

BASE_URL = "http://127.0.0.1:5000"


class HelpChainTester:
    def __init__(self):
        self.session = requests.Session()
        self.test_results = []
        self.admin_logged_in = False

    def log_test(self, test_name, success, message=""):
        """Log test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        result = f"{status} {test_name}: {message}"
        self.test_results.append(result)
        print(result)

    def test_homepage(self):
        """Test homepage accessibility"""
        try:
            response = self.session.get(f"{BASE_URL}/")
            success = response.status_code == 200
            self.log_test("Homepage", success, f"Status: {response.status_code}")
            return success
        except Exception as e:
            self.log_test("Homepage", False, f"Error: {e}")
            return False

    def test_admin_login(self):
        """Test admin login functionality"""
        try:
            # Test login page
            response = self.session.get(f"{BASE_URL}/admin_login")
            if response.status_code != 200:
                self.log_test(
                    "Admin Login Page", False, f"Status: {response.status_code}"
                )
                return False

            # Test login with correct credentials
            login_data = {"username": "admin", "password": os.getenv("ADMIN_PASSWORD", "Admin123")}
            response = self.session.post(
                f"{BASE_URL}/admin_login", data=login_data, allow_redirects=False
            )

            if response.status_code == 302:  # Redirect after successful login
                self.admin_logged_in = True
                self.log_test("Admin Login", True, "Login successful")
                return True
            else:
                self.log_test(
                    "Admin Login",
                    False,
                    f"Login failed, status: {response.status_code}",
                )
                return False
        except Exception as e:
            self.log_test("Admin Login", False, f"Error: {e}")
            return False

    def test_admin_dashboard(self):
        """Test admin dashboard access"""
        if not self.admin_logged_in:
            self.log_test("Admin Dashboard", False, "Not logged in")
            return False

        try:
            response = self.session.get(f"{BASE_URL}/admin_dashboard")
            success = response.status_code == 200
            self.log_test("Admin Dashboard", success, f"Status: {response.status_code}")
            return success
        except Exception as e:
            self.log_test("Admin Dashboard", False, f"Error: {e}")
            return False

    def test_analytics(self):
        """Test analytics functionality"""
        if not self.admin_logged_in:
            self.log_test("Analytics", False, "Not logged in")
            return False

        try:
            response = self.session.get(f"{BASE_URL}/admin_analytics")
            success = response.status_code == 200
            if success:
                content = response.text.lower()
                has_analytics = (
                    "analytics" in content
                    or "total" in content
                    or "requests" in content
                )
                self.log_test(
                    "Analytics",
                    has_analytics,
                    (
                        "Analytics data present"
                        if has_analytics
                        else "No analytics content found"
                    ),
                )
                return has_analytics
            else:
                self.log_test("Analytics", False, f"Status: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Analytics", False, f"Error: {e}")
            return False

    def test_volunteers(self):
        """Test volunteers functionality"""
        if not self.admin_logged_in:
            self.log_test("Volunteers", False, "Not logged in")
            return False

        try:
            response = self.session.get(f"{BASE_URL}/admin_volunteers")
            success = response.status_code == 200
            self.log_test("Volunteers Page", success, f"Status: {response.status_code}")
            return success
        except Exception as e:
            self.log_test("Volunteers Page", False, f"Error: {e}")
            return False

    def test_help_requests(self):
        """Test help requests functionality"""
        try:
            # Test public help request form
            response = self.session.get(f"{BASE_URL}/help_request")
            form_accessible = response.status_code == 200

            # Test submitting a help request
            help_data = {
                "name": "Test User",
                "email": "test@example.com",
                "phone": "+359123456789",
                "location": "Sofia",
                "help_type": "food",
                "description": "Test help request for integration testing",
                "urgency": "medium",
            }
            response = self.session.post(
                f"{BASE_URL}/help_request", data=help_data, allow_redirects=False
            )
            submission_success = response.status_code in [
                200,
                302,
            ]  # Success or redirect

            success = form_accessible and submission_success
            self.log_test(
                "Help Requests",
                success,
                f"Form: {form_accessible}, Submit: {submission_success}",
            )
            return success
        except Exception as e:
            self.log_test("Help Requests", False, f"Error: {e}")
            return False

    def test_ai_chatbot(self):
        """Test AI chatbot functionality"""
        try:
            # Test chatbot page
            response = self.session.get(f"{BASE_URL}/chatbot")
            page_accessible = response.status_code == 200

            # Test API endpoint if available
            try:
                chat_data = {
                    "message": "Здравей, имам нужда от помощ с храна",
                    "context": "help_request",
                }
                response = self.session.post(f"{BASE_URL}/api/chat", json=chat_data)
                api_works = response.status_code == 200
                if api_works:
                    data = response.json()
                    has_response = "response" in data
                    self.log_test(
                        "AI Chatbot",
                        has_response,
                        (
                            "AI response generated"
                            if has_response
                            else "No response in API"
                        ),
                    )
                    return has_response
                else:
                    self.log_test(
                        "AI Chatbot", False, f"API status: {response.status_code}"
                    )
                    return False
            except Exception:
                # If API not available, just check page
                self.log_test(
                    "AI Chatbot", page_accessible, "Page accessible (API not tested)"
                )
                return page_accessible
        except Exception as e:
            self.log_test("AI Chatbot", False, f"Error: {e}")
            return False

    def test_feedback(self):
        """Test feedback functionality"""
        try:
            # Test feedback page
            response = self.session.get(f"{BASE_URL}/feedback")
            page_accessible = response.status_code == 200

            # Test submitting feedback
            feedback_data = {
                "name": "Test User",
                "email": "feedback@example.com",
                "message": "This is a test feedback message for integration testing",
            }
            response = self.session.post(
                f"{BASE_URL}/feedback", data=feedback_data, allow_redirects=False
            )
            submission_success = response.status_code in [200, 302]

            success = page_accessible and submission_success
            self.log_test(
                "Feedback",
                success,
                f"Form: {page_accessible}, Submit: {submission_success}",
            )
            return success
        except Exception as e:
            self.log_test("Feedback", False, f"Error: {e}")
            return False

    def test_gamification(self):
        """Test gamification features"""
        try:
            # Test leaderboard if available
            response = self.session.get(f"{BASE_URL}/leaderboard")
            leaderboard_works = response.status_code == 200

            # Test user profile/stats if logged in
            if self.admin_logged_in:
                response = self.session.get(f"{BASE_URL}/profile")
                response.status_code == 200  # Just check accessibility

            success = leaderboard_works
            self.log_test("Gamification", success, f"Leaderboard: {leaderboard_works}")
            return success
        except Exception as e:
            self.log_test("Gamification", False, f"Error: {e}")
            return False

    def test_admin_2fa(self):
        """Test 2FA functionality for admin"""
        if not self.admin_logged_in:
            self.log_test("Admin 2FA", False, "Not logged in")
            return False

        try:
            # Test 2FA setup page
            response = self.session.get(f"{BASE_URL}/admin_2fa_setup")
            setup_accessible = response.status_code == 200

            # Test 2FA verification (would need actual token)
            # For testing, we'll just check if the endpoint exists
            response = self.session.get(f"{BASE_URL}/admin_2fa_verify")
            response.status_code in [200, 302]  # May redirect if not set up

            success = setup_accessible
            self.log_test("Admin 2FA", success, f"Setup: {setup_accessible}")
            return success
        except Exception as e:
            self.log_test("Admin 2FA", False, f"Error: {e}")
            return False

    def test_api_endpoints(self):
        """Test various API endpoints"""
        try:
            results = []

            # Test analytics API
            if self.admin_logged_in:
                response = self.session.get(f"{BASE_URL}/api/analytics/dashboard")
                results.append(("Analytics API", response.status_code == 200))

            # Test volunteers API
            response = self.session.get(f"{BASE_URL}/api/volunteers")
            results.append(("Volunteers API", response.status_code == 200))

            # Test help requests API
            response = self.session.get(f"{BASE_URL}/api/help_requests")
            results.append(("Help Requests API", response.status_code == 200))

            success = any(status for _, status in results)
            api_results = ", ".join(
                [f"{name}: {'OK' if status else 'FAIL'}" for name, status in results]
            )
            self.log_test("API Endpoints", success, api_results)
            return success
        except Exception as e:
            self.log_test("API Endpoints", False, f"Error: {e}")
            return False

    def run_all_tests(self):
        """Run all tests"""
        print("🚀 Starting HelpChain Integration Tests")
        print("=" * 50)

        # Wait a moment for server to be ready
        time.sleep(2)

        tests = [
            self.test_homepage,
            self.test_admin_login,
            self.test_admin_dashboard,
            self.test_analytics,
            self.test_volunteers,
            self.test_help_requests,
            self.test_ai_chatbot,
            self.test_feedback,
            self.test_gamification,
            self.test_admin_2fa,
            self.test_api_endpoints,
        ]

        passed = 0
        total = len(tests)

        for test in tests:
            if test():
                passed += 1
            time.sleep(0.5)  # Small delay between tests

        print("\n" + "=" * 50)
        print(f"📊 Test Results: {passed}/{total} tests passed")

        if passed == total:
            print("🎉 All tests passed! HelpChain is working correctly.")
        elif passed >= total * 0.8:
            print("✅ Most tests passed. Minor issues detected.")
        else:
            print("⚠️ Several tests failed. Check the application configuration.")

        return passed, total


def main():
    tester = HelpChainTester()
    passed, total = tester.run_all_tests()

    # Save detailed results to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"test_results_{timestamp}.txt"

    with open(filename, "w", encoding="utf-8") as f:
        f.write("HelpChain Integration Test Results\n")
        f.write("=" * 50 + "\n")
        f.write(f"Date: {datetime.now()}\n")
        f.write(f"Tests Passed: {passed}/{total}\n\n")
        f.write("Detailed Results:\n")
        for result in tester.test_results:
            f.write(result + "\n")

    print(f"\n📄 Detailed results saved to: {filename}")

    # Exit with appropriate code
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
