"""
Simple Load Testing for HelpChain Application

This script provides comprehensive load testing using Python's built-in libraries
to avoid complex dependency issues. It simulates different user types and measures
performance under various loads.

Usage:
    python load_test.py [users] [duration_seconds]

Example:
    python load_test.py 50 60  # 50 concurrent users for 60 seconds
"""

import concurrent.futures
import json
import random
import requests
import statistics
import threading
import time
from collections import defaultdict


class LoadTester:
    """Simple load testing framework for HelpChain"""

    def __init__(self, base_url: str = "http://localhost:5000"):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.results = defaultdict(list)
        self.errors = []
        self.start_time = None
        self.end_time = None

    def run_load_test(self, num_users, duration_seconds):
        """Run load test with specified number of users for given duration"""
        print(f"🚀 Starting load test: {num_users} users for {duration_seconds} seconds")
        print(f"🎯 Target: {self.base_url}")

        self.start_time = time.time()
        self.results = defaultdict(list)
        self.errors = []

        # Create thread pool
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_users) as executor:
            # Submit user simulation tasks
            futures = []
            for user_id in range(num_users):
                future = executor.submit(self._simulate_user, user_id, duration_seconds)
                futures.append(future)

            # Wait for all users to complete
            concurrent.futures.wait(futures)

        self.end_time = time.time()

        # Calculate results
        return self._calculate_results()

    def _simulate_user(self, user_id: int, duration_seconds: int):
        """Simulate a single user session"""
        user_type = random.choice(['volunteer', 'admin', 'mixed', 'public'])
        user_start_time = time.time()

        while time.time() - user_start_time < duration_seconds:
            try:
                if user_type == 'volunteer':
                    self._volunteer_actions(user_id)
                elif user_type == 'admin':
                    self._admin_actions(user_id)
                elif user_type == 'mixed':
                    self._mixed_actions(user_id)
                else:
                    self._public_actions(user_id)

                # Random think time between actions (1-3 seconds)
                time.sleep(random.uniform(1, 3))

            except Exception as e:
                error_msg = f"User {user_id} ({user_type}): {str(e)}"
                self.errors.append(error_msg)
                print(f"❌ {error_msg}")

    def _volunteer_actions(self, user_id: int):
        """Simulate volunteer user actions"""
        actions = [
            ('dashboard', lambda: self._api_call('GET', '/api/volunteer/dashboard')),
            ('tasks', lambda: self._api_call('GET', '/api/volunteer/tasks')),
            ('profile', lambda: self._api_call('GET', '/api/user/profile')),
            ('notifications', lambda: self._api_call('GET', '/api/notifications')),
        ]

        action_name, action_func = random.choice(actions)
        start_time = time.time()
        success = action_func()
        response_time = (time.time() - start_time) * 1000

        self.results[f'volunteer_{action_name}'].append({
            'response_time': response_time,
            'success': success,
            'user_id': user_id
        })

    def _admin_actions(self, user_id: int):
        """Simulate admin user actions"""
        actions = [
            ('dashboard', lambda: self._api_call('GET', '/api/admin/dashboard')),
            ('analytics', lambda: self._api_call('GET', '/api/analytics/dashboard')),
            ('volunteers', lambda: self._api_call('GET', '/api/admin/volunteers')),
            ('ai_status', lambda: self._api_call('GET', '/api/ai/status')),
        ]

        action_name, action_func = random.choice(actions)
        start_time = time.time()
        success = action_func()
        response_time = (time.time() - start_time) * 1000

        self.results[f'admin_{action_name}'].append({
            'response_time': response_time,
            'success': success,
            'user_id': user_id
        })

    def _mixed_actions(self, user_id: int):
        """Simulate mixed user actions"""
        actions = [
            ('volunteer_dashboard', lambda: self._api_call('GET', '/api/volunteer/dashboard')),
            ('admin_dashboard', lambda: self._api_call('GET', '/api/admin/dashboard')),
            ('profile', lambda: self._api_call('GET', '/api/user/profile')),
            ('ai_status', lambda: self._api_call('GET', '/api/ai/status')),
        ]

        action_name, action_func = random.choice(actions)
        start_time = time.time()
        success = action_func()
        response_time = (time.time() - start_time) * 1000

        self.results[f'mixed_{action_name}'].append({
            'response_time': response_time,
            'success': success,
            'user_id': user_id
        })

    def _public_actions(self, user_id: int):
        """Simulate public user actions"""
        actions = [
            ('homepage', lambda: self._api_call('GET', '/')),
            ('static_css', lambda: self._api_call('GET', '/static/styles.css')),
            ('static_js', lambda: self._api_call('GET', '/static/jquery.min.js')),
            ('error_page', lambda: self._api_call('GET', '/nonexistent')),
        ]

        action_name, action_func = random.choice(actions)
        start_time = time.time()
        success = action_func()
        response_time = (time.time() - start_time) * 1000

        self.results[f'public_{action_name}'].append({
            'response_time': response_time,
            'success': success,
            'user_id': user_id
        })

    def _api_call(self, method, endpoint, data=None):
        """Make API call and return success status"""
        try:
            url = f"{self.base_url}{endpoint}"
            headers = {'Content-Type': 'application/json'}

            if method == 'GET':
                response = self.session.get(url, headers=headers, timeout=10)
            elif method == 'POST':
                response = self.session.post(url, json=data, headers=headers, timeout=10)
            elif method == 'PUT':
                response = self.session.put(url, json=data, headers=headers, timeout=10)
            else:
                return False

            # Consider 2xx and 4xx (expected errors) as successful for load testing
            return response.status_code < 500

        except requests.exceptions.RequestException:
            return False

    def _calculate_results(self):
        """Calculate comprehensive test results"""
        total_duration = self.end_time - self.start_time
        total_requests = sum(len(requests) for requests in self.results.values())

        results = {
            'test_duration': total_duration,
            'total_requests': total_requests,
            'requests_per_second': total_requests / total_duration if total_duration > 0 else 0,
            'errors': len(self.errors),
            'error_rate': len(self.errors) / total_requests if total_requests > 0 else 0,
            'endpoint_results': {}
        }

        # Calculate per-endpoint statistics
        for endpoint, request_list in self.results.items():
            if not request_list:
                continue

            response_times = [r['response_time'] for r in request_list]
            successful_requests = [r for r in request_list if r['success']]

            results['endpoint_results'][endpoint] = {
                'total_requests': len(request_list),
                'successful_requests': len(successful_requests),
                'success_rate': len(successful_requests) / len(request_list),
                'avg_response_time': statistics.mean(response_times),
                'median_response_time': statistics.median(response_times),
                'min_response_time': min(response_times),
                'max_response_time': max(response_times),
                'p95_response_time': statistics.quantiles(response_times, n=20)[18] if len(response_times) >= 20 else max(response_times),
                'p99_response_time': statistics.quantiles(response_times, n=100)[98] if len(response_times) >= 100 else max(response_times)
            }

        return results


def print_results(results):
    """Print formatted test results"""
    print("\n" + "="*80)
    print("📊 LOAD TEST RESULTS")
    print("="*80)

    print(".2f")
    print(f"📈 Requests/second: {results['requests_per_second']:.2f}")
    print(f"❌ Errors: {results['errors']} ({results['error_rate']*100:.1f}%)")
    print(f"📋 Total requests: {results['total_requests']}")

    print("\n" + "-"*80)
    print("ENDPOINT PERFORMANCE")
    print("-"*80)

    for endpoint, stats in results['endpoint_results'].items():
        print(f"\n🔹 {endpoint}")
        print(f"   Requests: {stats['total_requests']} (Success: {stats['success_rate']*100:.1f}%)")
        print(f"   Response Time - Avg: {stats['avg_response_time']:.2f}ms, Median: {stats['median_response_time']:.2f}ms")
        print(f"   Response Time - Min: {stats['min_response_time']:.2f}ms, Max: {stats['max_response_time']:.2f}ms")
        print(f"   Response Time - P95: {stats['p95_response_time']:.2f}ms, P99: {stats['p99_response_time']:.2f}ms")

    print("\n" + "="*80)


def run_scenario(scenario_name: str):
    """Run predefined test scenarios"""
    scenarios = {
        'light': {'users': 5, 'duration': 30, 'desc': 'Light load (5 users, 30s)'},
        'medium': {'users': 20, 'duration': 60, 'desc': 'Medium load (20 users, 1min)'},
        'heavy': {'users': 50, 'duration': 120, 'desc': 'Heavy load (50 users, 2min)'},
        'stress': {'users': 100, 'duration': 180, 'desc': 'Stress test (100 users, 3min)'}
    }

    if scenario_name not in scenarios:
        print(f"❌ Unknown scenario: {scenario_name}")
        print(f"Available: {', '.join(scenarios.keys())}")
        return

    config = scenarios[scenario_name]
    print(f"🎯 Running scenario: {config['desc']}")

    tester = LoadTester()
    results = tester.run_load_test(config['users'], config['duration'])
    print_results(results)


def main():
    """Main entry point"""
    import sys

    if len(sys.argv) == 2:
        # Run predefined scenario
        scenario = sys.argv[1]
        run_scenario(scenario)
    elif len(sys.argv) == 3:
        # Custom test: users duration
        try:
            users = int(sys.argv[1])
            duration = int(sys.argv[2])

            tester = LoadTester()
            results = tester.run_load_test(users, duration)
            print_results(results)
        except ValueError:
            print("❌ Invalid arguments. Use: python load_test.py <users> <duration_seconds>")
    else:
        print("HelpChain Load Testing")
        print("======================")
        print("Usage:")
        print("  python load_test.py <scenario>")
        print("  python load_test.py <users> <duration_seconds>")
        print("\nScenarios:")
        print("  light   - 5 users for 30 seconds")
        print("  medium  - 20 users for 1 minute")
        print("  heavy   - 50 users for 2 minutes")
        print("  stress  - 100 users for 3 minutes")
        print("\nExamples:")
        print("  python load_test.py light")
        print("  python load_test.py 25 90")


if __name__ == "__main__":
    main()