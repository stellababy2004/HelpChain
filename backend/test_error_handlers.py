#!/usr/bin/env python3
"""
Test script to verify error handling implementation
Tests various error conditions to ensure proper error responses
"""

import json
import requests
import time
from typing import Any


class ErrorHandlerTester:
    def __init__(self, base_url: str = "http://127.0.0.1:5000"):
        self.base_url = base_url
        self.session = requests.Session()

    def test_error_handler(
        self, endpoint: str, expected_status: int, description: str
    ) -> dict[str, Any]:
        """Test a specific error endpoint"""
        try:
            url = f"{self.base_url}{endpoint}"
            response = self.session.get(url, timeout=10)

            result = {
                "endpoint": endpoint,
                "expected_status": expected_status,
                "actual_status": response.status_code,
                "description": description,
                "success": response.status_code == expected_status,
                "content_type": response.headers.get("content-type", ""),
                "has_html": "text/html" in response.headers.get("content-type", ""),
                "response_size": len(response.text),
            }

            if result["success"]:
                print(
                    f"✅ {description}: Status {response.status_code} (expected {expected_status})"
                )
            else:
                print(
                    f"❌ {description}: Status {response.status_code} (expected {expected_status})"
                )

            return result

        except requests.exceptions.RequestException as e:
            print(f"❌ {description}: Request failed - {e}")
            return {
                "endpoint": endpoint,
                "expected_status": expected_status,
                "description": description,
                "success": False,
                "error": str(e),
            }

    def test_all_error_handlers(self):
        """Test all implemented error handlers"""
        print("🧪 Testing Error Handlers\n")

        test_cases = [
            # HTTP Error Codes
            ("/nonexistent", 404, "404 Not Found - Non-existent page"),
            ("/api/invalid", 404, "404 Not Found - Invalid API endpoint"),
            # Custom error endpoints (now available)
            ("/test/trigger-400", 400, "400 Bad Request - Custom trigger"),
            ("/test/trigger-401", 401, "401 Unauthorized - Custom trigger"),
            ("/test/trigger-429", 429, "429 Too Many Requests - Custom trigger"),
            (
                "/test/trigger-validation-error",
                400,
                "400 Bad Request - Validation error",
            ),
            (
                "/test/trigger-database-error",
                500,
                "500 Internal Server Error - Database error",
            ),
        ]

        results = []
        for endpoint, expected_status, description in test_cases:
            result = self.test_error_handler(endpoint, expected_status, description)
            results.append(result)
            time.sleep(0.5)  # Brief pause between requests

        return results

    def test_normal_endpoints(self):
        """Test that normal endpoints still work"""
        print("\n🔍 Testing Normal Endpoints\n")

        test_cases = [
            ("/", 200, "Home page"),
            ("/api", 200, "API root"),
        ]

        results = []
        for endpoint, expected_status, description in test_cases:
            result = self.test_error_handler(endpoint, expected_status, description)
            results.append(result)
            time.sleep(0.5)

        return results

    def generate_report(self, error_results: list, normal_results: list):
        """Generate a comprehensive test report"""
        print("\n📊 Error Handler Test Report")
        print("=" * 50)

        # Error handler results
        successful_errors = sum(1 for r in error_results if r.get("success", False))
        total_errors = len(error_results)

        print(f"Error Handlers: {successful_errors}/{total_errors} passed")

        # Normal endpoint results
        successful_normal = sum(1 for r in normal_results if r.get("success", False))
        total_normal = len(normal_results)

        print(f"Normal Endpoints: {successful_normal}/{total_normal} passed")

        # Detailed results
        print("\nDetailed Results:")
        print("-" * 30)

        all_results = error_results + normal_results
        for result in all_results:
            status = "✅" if result.get("success", False) else "❌"
            endpoint = result.get("endpoint", "Unknown")
            expected = result.get("expected_status", "Unknown")
            actual = result.get("actual_status", result.get("error", "Failed"))
            desc = result.get("description", "")

            print(f"{status} {endpoint} - {desc}")
            if not result.get("success", False):
                print(f"   Expected: {expected}, Got: {actual}")

        # Summary
        total_passed = successful_errors + successful_normal
        total_tests = total_errors + total_normal

        print(f"\nOverall: {total_passed}/{total_tests} tests passed")

        if total_passed == total_tests:
            print("🎉 All error handlers are working correctly!")
        else:
            print("⚠️  Some tests failed. Check the detailed results above.")

        return {
            "error_handlers": {"passed": successful_errors, "total": total_errors},
            "normal_endpoints": {"passed": successful_normal, "total": total_normal},
            "overall": {"passed": total_passed, "total": total_tests},
        }


def main():
    """Main test execution"""
    print("🚀 Starting Error Handler Tests")
    print("Make sure the Flask app is running on http://127.0.0.1:5000")
    print()

    tester = ErrorHandlerTester()

    # Test error handlers
    error_results = tester.test_all_error_handlers()

    # Test normal functionality
    normal_results = tester.test_normal_endpoints()

    # Generate report
    report = tester.generate_report(error_results, normal_results)

    return report


if __name__ == "__main__":
    main()
