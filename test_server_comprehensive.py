#!/usr/bin/env python3
"""
Comprehensive test suite for HelpChain Flask server
Tests all major functionality including server startup, admin authentication, and API endpoints
"""

import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import requests

# Add backend directory to path
backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))


class HelpChainTester:
    def __init__(self):
        self.base_url = "http://127.0.0.1:5000"
        self.server_process = None
        self.server_thread = None
        self.test_results = []

    def log_test(self, test_name, success, message=""):
        """Log test result"""
        status = "PASS" if success else "FAIL"
        result = f"{status}: {test_name}"
        if message:
            result += f" - {message}"
        self.test_results.append(result)
        print(result)

    def start_server(self):
        """Start the Flask server in a separate process"""
        try:
            print("Starting HelpChain server...")
            self.server_process = subprocess.Popen(
                [sys.executable, "backend/appy.py"],
                cwd=Path(__file__).parent,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            # Wait for server to start
            time.sleep(5)

            # Check if server is running
            try:
                response = requests.get(f"{self.base_url}/", timeout=5)
                return response.status_code == 200
            except:
                return False

        except Exception as e:
            print(f"Failed to start server: {e}")
            return False

    def stop_server(self):
        """Stop the Flask server"""
        if self.server_process:
            try:
                self.server_process.terminate()
                self.server_process.wait(timeout=10)
                print("Server stopped successfully")
            except:
                self.server_process.kill()
                print("Server force killed")

    def test_admin_login_page(self):
        """Test admin login page accessibility"""
        try:
            response = requests.get(f"{self.base_url}/admin/login", timeout=5)
            success = response.status_code == 200
            self.log_test(
                "Admin login page", success, f"Status: {response.status_code}"
            )
            return success
        except Exception as e:
            self.log_test("Admin login page", False, str(e))
            return False

    def test_admin_authentication(self):
        """Test admin authentication with default credentials"""
        try:
            # Create a session to maintain cookies
            session = requests.Session()

            # First get the login page to establish session
            login_page = session.get(f"{self.base_url}/admin/login", timeout=5)
            if login_page.status_code != 200:
                self.log_test("Admin authentication", False, "Cannot access login page")
                return False

            # Try to login with default credentials (admin/admin123)
            login_data = {"username": "admin", "password": "admin123"}

            response = session.post(
                f"{self.base_url}/admin/login",
                data=login_data,
                timeout=5,
                allow_redirects=True,
            )

            # Check if redirected to dashboard (successful login)
            success = (
                response.url.endswith("/admin/dashboard")
                or "admin/dashboard" in response.url
            )
            self.log_test("Admin authentication", success, f"Final URL: {response.url}")
            return success

        except Exception as e:
            self.log_test("Admin authentication", False, str(e))
            return False

    def test_admin_dashboard(self):
        """Test admin dashboard accessibility after login"""
        try:
            # Create a session and login first
            session = requests.Session()

            # Login
            login_data = {"username": "admin", "password": "admin123"}

            login_response = session.post(
                f"{self.base_url}/admin/login",
                data=login_data,
                timeout=5,
                allow_redirects=True,
            )

            if not (
                login_response.url.endswith("/admin/dashboard")
                or "admin/dashboard" in login_response.url
            ):
                self.log_test("Admin dashboard", False, "Login failed")
                return False

            # Now access dashboard directly
            dashboard_response = session.get(
                f"{self.base_url}/admin/dashboard", timeout=5
            )
            success = dashboard_response.status_code == 200
            self.log_test(
                "Admin dashboard", success, f"Status: {dashboard_response.status_code}"
            )
            return success

        except Exception as e:
            self.log_test("Admin dashboard", False, str(e))
            return False

    def test_api_endpoints(self):
        """Test various API endpoints"""
        endpoints = [
            "/",
            "/analytics",
            "/api/analytics/data",
            "/set_language/en",
            "/set_language/bg",
        ]

        all_success = True
        for endpoint in endpoints:
            try:
                response = requests.get(f"{self.base_url}{endpoint}", timeout=5)
                success = response.status_code == 200
                self.log_test(
                    f"API endpoint {endpoint}",
                    success,
                    f"Status: {response.status_code}",
                )
                if not success:
                    all_success = False
            except Exception as e:
                self.log_test(f"API endpoint {endpoint}", False, str(e))
                all_success = False

        return all_success

    def test_static_files(self):
        """Test static file serving"""
        try:
            response = requests.get(f"{self.base_url}/static/styles.css", timeout=5)
            success = response.status_code == 200
            self.log_test("Static files", success, f"Status: {response.status_code}")
            return success
        except Exception as e:
            self.log_test("Static files", False, str(e))
            return False

    def run_all_tests(self):
        """Run all tests"""
        print("=" * 60)
        print("HelpChain Server Comprehensive Test Suite")
        print("=" * 60)

        # Start server
        if not self.start_server():
            print("CRITICAL: Cannot start server - aborting tests")
            return False

        try:
            # Run tests
            tests = [
                self.test_admin_login_page,
                self.test_admin_authentication,
                self.test_admin_dashboard,
                self.test_api_endpoints,
                self.test_static_files,
            ]

            all_passed = True
            for test in tests:
                if not test():
                    all_passed = False

            # Summary
            print("\n" + "=" * 60)
            print("TEST SUMMARY")
            print("=" * 60)

            passed = sum(1 for result in self.test_results if result.startswith("PASS"))
            failed = sum(1 for result in self.test_results if result.startswith("FAIL"))
            total = len(self.test_results)

            print(f"Total tests: {total}")
            print(f"Passed: {passed}")
            print(f"Failed: {failed}")
            print(
                f"Success rate: {passed / total * 100:.1f}%"
                if total > 0
                else "No tests run"
            )

            if all_passed:
                print("\n🎉 ALL TESTS PASSED! HelpChain server is fully functional.")
            else:
                print("\n❌ Some tests failed. Check the output above for details.")

            return all_passed

        finally:
            self.stop_server()


def main():
    """Main test runner"""
    tester = HelpChainTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
