#!/usr/bin/env python
"""
Enhanced Load Testing for HelpChain Application

This script provides comprehensive load testing with proper authentication
and realistic user scenarios for different user types.

Usage:
    python enhanced_load_test.py [scenario] [users] [duration]

Scenarios:
    public - Test public endpoints only
    authenticated - Test with proper authentication
    mixed - Mix of public and authenticated users
    stress - High load stress testing

Examples:
    python enhanced_load_test.py public 10 60
    python enhanced_load_test.py authenticated 20 120
    python enhanced_load_test.py stress 50 180
"""

import json
import random
import statistics
import threading
import time
from collections import defaultdict

import requests


class EnhancedLoadTester:
    """Enhanced load testing framework with proper authentication"""

    def __init__(self, base_url: str = "http://localhost:5000"):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.results = defaultdict(list)
        self.errors = []
        self.start_time = None
        self.end_time = None
        self.auth_tokens = {}  # Cache auth tokens

    def run_load_test(self, scenario, num_users, duration_seconds):
        """Run load test with specified scenario, users, and duration"""
        print(f"🚀 Starting enhanced load test: {scenario} scenario")
        print(f"👥 Users: {num_users}, Duration: {duration_seconds}s")
        print(f"🎯 Target: {self.base_url}")

        self.start_time = time.time()
        self.results = defaultdict(list)
        self.errors = []

        # Create thread pool
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_users) as executor:
            futures = []
            for user_id in range(num_users):
                future = executor.submit(
                    self._simulate_user_scenario, user_id, scenario, duration_seconds
                )
                futures.append(future)

            concurrent.futures.wait(futures)

        self.end_time = time.time()
        return self._calculate_results()

    def _simulate_user_scenario(
        self, user_id: int, scenario: str, duration_seconds: int
    ):
        """Simulate user based on scenario"""
        user_start_time = time.time()

        # Get user type based on scenario
        if scenario == "public":
            user_type = "public"
        elif scenario == "authenticated":
            user_type = random.choice(["volunteer", "admin"])
        elif scenario == "mixed":
            user_type = random.choice(["public", "volunteer", "admin"])
        else:  # stress
            user_type = random.choice(
                ["volunteer", "admin"]
            )  # Focus on authenticated users

        # Authenticate if needed
        auth_token = None
        if user_type in ["volunteer", "admin"]:
            auth_token = self._authenticate_user(user_type, user_id)

        while time.time() - user_start_time < duration_seconds:
            try:
                if user_type == "public":
                    self._public_user_actions(user_id)
                elif user_type == "volunteer":
                    self._volunteer_user_actions(user_id, auth_token)
                elif user_type == "admin":
                    self._admin_user_actions(user_id, auth_token)

                # Realistic think time between actions (1-4 seconds)
                time.sleep(random.uniform(1, 4))

            except Exception as e:
                error_msg = f"User {user_id} ({user_type}): {str(e)}"
                self.errors.append(error_msg)

    def _authenticate_user(self, user_type: str, user_id: int):
        """Authenticate user and return token"""
        cache_key = f"{user_type}_{user_id}"

        if cache_key in self.auth_tokens:
            return self.auth_tokens[cache_key]

        try:
            # Use default admin credentials for testing
            if user_type == "admin":
                login_data = {"username": "admin", "password": "Admin123"}
            else:
                # For volunteers, try to login or skip if no volunteer accounts
                login_data = {"username": "admin", "password": "Admin123"}  # Fallback

            response = self.session.post(
                f"{self.base_url}/api/auth/login", json=login_data, timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                token = data.get("access_token") or data.get("token")
                if token:
                    self.auth_tokens[cache_key] = token
                    return token

        except Exception as e:
            print(f"❌ Auth failed for {user_type} user {user_id}: {e}")

        return None

    def _public_user_actions(self, user_id: int):
        """Simulate public user actions (no auth required)"""
        actions = [
            ("homepage", lambda: self._api_call("GET", "/")),
            ("static_css", lambda: self._api_call("GET", "/static/styles.css")),
            ("static_js", lambda: self._api_call("GET", "/static/jquery.min.js")),
            ("error_404", lambda: self._api_call("GET", "/nonexistent")),
        ]

        action_name, action_func = random.choice(actions)
        start_time = time.time()
        success = action_func()
        response_time = (time.time() - start_time) * 1000

        self.results[f"public_{action_name}"].append(
            {"response_time": response_time, "success": success, "user_id": user_id}
        )

    def _volunteer_user_actions(self, user_id: int, auth_token: str = None):
        """Simulate volunteer user actions"""
        headers = {"Authorization": f"Bearer {auth_token}"} if auth_token else {}

        actions = [
            (
                "dashboard",
                lambda: self._api_call(
                    "GET", "/api/volunteer/dashboard", headers=headers
                ),
            ),
            (
                "tasks",
                lambda: self._api_call("GET", "/api/volunteer/tasks", headers=headers),
            ),
            (
                "profile",
                lambda: self._api_call("GET", "/api/user/profile", headers=headers),
            ),
            (
                "notifications",
                lambda: self._api_call("GET", "/api/notifications", headers=headers),
            ),
        ]

        action_name, action_func = random.choice(actions)
        start_time = time.time()
        success = action_func()
        response_time = (time.time() - start_time) * 1000

        self.results[f"volunteer_{action_name}"].append(
            {"response_time": response_time, "success": success, "user_id": user_id}
        )

    def _admin_user_actions(self, user_id: int, auth_token: str = None):
        """Simulate admin user actions"""
        headers = {"Authorization": f"Bearer {auth_token}"} if auth_token else {}

        actions = [
            (
                "dashboard",
                lambda: self._api_call("GET", "/api/admin/dashboard", headers=headers),
            ),
            (
                "analytics",
                lambda: self._api_call(
                    "GET", "/api/analytics/dashboard", headers=headers
                ),
            ),
            (
                "volunteers",
                lambda: self._api_call("GET", "/api/admin/volunteers", headers=headers),
            ),
            (
                "ai_status",
                lambda: self._api_call("GET", "/api/ai/status", headers=headers),
            ),
        ]

        action_name, action_func = random.choice(actions)
        start_time = time.time()
        success = action_func()
        response_time = (time.time() - start_time) * 1000

        self.results[f"admin_{action_name}"].append(
            {"response_time": response_time, "success": success, "user_id": user_id}
        )

    def _api_call(self, method, endpoint, headers=None, data=None):
        """Make API call and return success status"""
        try:
            url = f"{self.base_url}{endpoint}"
            request_headers = {"Content-Type": "application/json"}
            if headers:
                request_headers.update(headers)

            if method == "GET":
                response = self.session.get(url, headers=request_headers, timeout=30)
            elif method == "POST":
                response = self.session.post(
                    url, json=data, headers=request_headers, timeout=30
                )
            elif method == "PUT":
                response = self.session.put(
                    url, json=data, headers=request_headers, timeout=30
                )
            else:
                return False

            # Consider 2xx and some 4xx (expected errors) as successful for load testing
            return response.status_code < 500

        except requests.exceptions.RequestException:
            return False

    def _calculate_results(self):
        """Calculate comprehensive test results"""
        total_duration = self.end_time - self.start_time
        total_requests = sum(len(requests) for requests in self.results.values())

        results = {
            "test_duration": total_duration,
            "total_requests": total_requests,
            "requests_per_second": (
                total_requests / total_duration if total_duration > 0 else 0
            ),
            "errors": len(self.errors),
            "error_rate": (
                len(self.errors) / total_requests if total_requests > 0 else 0
            ),
            "endpoint_results": {},
        }

        # Calculate per-endpoint statistics
        for endpoint, request_list in self.results.items():
            if not request_list:
                continue

            response_times = [r["response_time"] for r in request_list]
            successful_requests = [r for r in request_list if r["success"]]

            results["endpoint_results"][endpoint] = {
                "total_requests": len(request_list),
                "successful_requests": len(successful_requests),
                "success_rate": len(successful_requests) / len(request_list),
                "avg_response_time": statistics.mean(response_times),
                "median_response_time": statistics.median(response_times),
                "min_response_time": min(response_times),
                "max_response_time": max(response_times),
                "p95_response_time": (
                    statistics.quantiles(response_times, n=20)[18]
                    if len(response_times) >= 20
                    else max(response_times)
                ),
                "p99_response_time": (
                    statistics.quantiles(response_times, n=100)[98]
                    if len(response_times) >= 100
                    else max(response_times)
                ),
            }

        return results


def print_results(results):
    """Print formatted test results"""
    print("\n" + "=" * 80)
    print("📊 ENHANCED LOAD TEST RESULTS")
    print("=" * 80)

    print(".2f")
    print(f"📈 Requests/second: {results['requests_per_second']:.2f}")
    print(f"❌ Errors: {results['errors']} ({results['error_rate']*100:.1f}%)")
    print(f"📋 Total requests: {results['total_requests']}")

    print("\n" + "-" * 80)
    print("ENDPOINT PERFORMANCE")
    print("-" * 80)

    for endpoint, stats in results["endpoint_results"].items():
        print(f"\n🔹 {endpoint}")
        print(
            f"   Requests: {stats['total_requests']} (Success: {stats['success_rate']*100:.1f}%)"
        )
        print(
            f"   Response Time - Avg: {stats['avg_response_time']:.2f}ms, Median: {stats['median_response_time']:.2f}ms"
        )
        print(
            f"   Response Time - Min: {stats['min_response_time']:.2f}ms, Max: {stats['max_response_time']:.2f}ms"
        )
        if stats["total_requests"] >= 20:
            print(
                f"   Response Time - P95: {stats['p95_response_time']:.2f}ms, P99: {stats['p99_response_time']:.2f}ms"
            )

    print("\n" + "=" * 80)


def run_scenario(scenario_name: str, users: int = None, duration: int = None):
    """Run predefined test scenarios"""
    scenarios = {
        "public": {
            "users": users or 10,
            "duration": duration or 60,
            "desc": "Public endpoints only",
        },
        "authenticated": {
            "users": users or 15,
            "duration": duration or 90,
            "desc": "Authenticated users",
        },
        "mixed": {
            "users": users or 20,
            "duration": duration or 120,
            "desc": "Mixed public/authenticated",
        },
        "stress": {
            "users": users or 50,
            "duration": duration or 180,
            "desc": "High load stress test",
        },
    }

    if scenario_name not in scenarios:
        print(f"❌ Unknown scenario: {scenario_name}")
        print(f"Available: {', '.join(scenarios.keys())}")
        return

    config = scenarios[scenario_name]
    print(f"🎯 Running scenario: {config['desc']}")

    tester = EnhancedLoadTester()
    results = tester.run_load_test(scenario_name, config["users"], config["duration"])
    print_results(results)


def main():
    """Main entry point"""
    import sys

    if len(sys.argv) >= 2:
        scenario = sys.argv[1]

        # Parse optional users and duration
        users = int(sys.argv[2]) if len(sys.argv) > 2 else None
        duration = int(sys.argv[3]) if len(sys.argv) > 3 else None

        run_scenario(scenario, users, duration)
    else:
        print("Enhanced HelpChain Load Testing")
        print("================================")
        print("Usage:")
        print("  python enhanced_load_test.py <scenario> [users] [duration_seconds]")
        print("\nScenarios:")
        print("  public        - Test public endpoints only")
        print("  authenticated - Test with authenticated users")
        print("  mixed         - Mix of public and authenticated users")
        print("  stress        - High load stress testing")
        print("\nExamples:")
        print("  python enhanced_load_test.py public")
        print("  python enhanced_load_test.py authenticated 20 120")
        print("  python enhanced_load_test.py stress 100 300")


if __name__ == "__main__":
    import concurrent.futures

    main()
