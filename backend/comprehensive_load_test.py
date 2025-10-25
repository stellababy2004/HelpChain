#!/usr/bin/env python
"""
Comprehensive Load Testing Suite for HelpChain

This script provides multiple load testing scenarios:
1. Basic connectivity test
2. Light load test (5-10 users)
3. Medium load test (20-50 users)
4. Heavy load test (50-100 users)
5. Stress test (100+ users)
6. Endurance test (sustained load over time)
7. Spike test (sudden load increases)
8. Mixed endpoint test (different API endpoints)

Usage:
    python comprehensive_load_test.py [scenario] [users] [duration]

Scenarios:
    basic     - Basic connectivity test
    light     - Light load (default: 10 users, 30s)
    medium    - Medium load (default: 30 users, 60s)
    heavy     - Heavy load (default: 75 users, 120s)
    stress    - Stress test (default: 150 users, 180s)
    endurance - Endurance test (default: 20 users, 300s)
    spike     - Spike test (default: 50->200->50 users)
    mixed     - Mixed endpoints test

Examples:
    python comprehensive_load_test.py basic
    python comprehensive_load_test.py light 15 45
    python comprehensive_load_test.py stress 200 300
"""

import concurrent.futures
import json
import random
import statistics
import threading
import time
from collections import defaultdict
from datetime import datetime

import requests


class ComprehensiveLoadTester:
    """Comprehensive load testing framework"""

    def __init__(
        self, base_url: str = "http://localhost:5001", test_name: str = "Load Test"
    ):
        self.base_url = base_url.rstrip("/")
        self.test_name = test_name
        self.session = requests.Session()
        self.results = defaultdict(list)
        self.errors = []
        self.start_time = None
        self.end_time = None
        self.metrics = {
            "response_times": [],
            "errors": [],
            "throughput": [],
            "concurrent_users": 0,
        }

    def run_basic_test(self):
        """Basic connectivity test"""
        print(f"🧪 Running basic connectivity test for {self.test_name}")

        try:
            start = time.time()
            response = requests.get(f"{self.base_url}/", timeout=5)
            end = time.time()

            result = {
                "endpoint": "/",
                "status_code": response.status_code,
                "response_time": (end - start) * 1000,
                "success": response.status_code == 200,
                "content_length": len(response.text),
            }

            print(f"✅ Basic test successful: {result['response_time']:.2f}ms")
            return result

        except Exception as e:
            print(f"❌ Basic test failed: {e}")
            return {"error": str(e)}

    def run_load_test(self, scenario, num_users, duration_seconds):
        """Run comprehensive load test"""
        print(
            f"🚀 Starting {scenario} load test: {num_users} users for {duration_seconds}s"
        )
        print(f"🎯 Target: {self.base_url}")
        print(f"📊 Test: {self.test_name}")

        self.start_time = time.time()
        self.results = defaultdict(list)
        self.errors = []
        self.metrics = {
            "response_times": [],
            "errors": [],
            "throughput": [],
            "concurrent_users": num_users,
        }

        # Create thread pool
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_users) as executor:
            futures = []
            for user_id in range(num_users):
                future = executor.submit(
                    self._simulate_user_scenario, user_id, scenario, duration_seconds
                )
                futures.append(future)

            # Monitor progress
            start_monitor = time.time()
            while not all(f.done() for f in futures):
                elapsed = time.time() - start_monitor
                completed = sum(1 for f in futures if f.done())
                if elapsed % 10 == 0:  # Report every 10 seconds
                    print(
                        f"📈 Progress: {completed}/{num_users} users completed ({elapsed:.0f}s elapsed)"
                    )
                time.sleep(1)

            concurrent.futures.wait(futures)

        self.end_time = time.time()
        return self._calculate_comprehensive_results(scenario)

    def _simulate_user_scenario(
        self, user_id: int, scenario: str, duration_seconds: int
    ):
        """Simulate user based on scenario"""
        user_start_time = time.time()

        while time.time() - user_start_time < duration_seconds:
            try:
                if scenario in ["light", "medium", "heavy", "stress"]:
                    self._standard_user_actions(user_id, scenario)
                elif scenario == "endurance":
                    self._endurance_user_actions(user_id)
                elif scenario == "spike":
                    self._spike_user_actions(user_id)
                elif scenario == "mixed":
                    self._mixed_endpoint_actions(user_id)
                else:
                    self._standard_user_actions(user_id, "light")

                # Realistic think time between actions (0.5-2 seconds)
                time.sleep(random.uniform(0.5, 2.0))

            except Exception as e:
                error_msg = f"User {user_id} ({scenario}): {str(e)}"
                self.errors.append(error_msg)

    def _standard_user_actions(self, user_id: int, intensity: str):
        """Standard user actions with varying intensity"""
        # Define action weights based on intensity
        weights = {
            "light": {"home": 5, "api_test": 3, "slow": 1},
            "medium": {"home": 4, "api_test": 3, "slow": 2},
            "heavy": {"home": 3, "api_test": 2, "slow": 3},
            "stress": {"home": 2, "api_test": 2, "slow": 4},
        }

        actions = []
        for action, weight in weights[intensity].items():
            actions.extend([action] * weight)

        action = random.choice(actions)

        if action == "home":
            endpoint = "/"
        elif action == "api_test":
            endpoint = "/api/test"
        else:  # slow
            endpoint = "/api/slow"

        start_time = time.time()
        success = self._api_call("GET", endpoint)
        response_time = (time.time() - start_time) * 1000

        self.results[endpoint].append(
            {
                "response_time": response_time,
                "success": success,
                "user_id": user_id,
                "timestamp": time.time(),
            }
        )

        self.metrics["response_times"].append(response_time)
        if not success:
            self.metrics["errors"].append(
                {"endpoint": endpoint, "user_id": user_id, "timestamp": time.time()}
            )

    def _endurance_user_actions(self, user_id: int):
        """Endurance test - consistent load over time"""
        endpoints = ["/", "/api/test", "/api/slow"]
        endpoint = random.choice(endpoints)

        start_time = time.time()
        success = self._api_call("GET", endpoint)
        response_time = (time.time() - start_time) * 1000

        self.results[endpoint].append(
            {
                "response_time": response_time,
                "success": success,
                "user_id": user_id,
                "timestamp": time.time(),
            }
        )

    def _spike_user_actions(self, user_id: int):
        """Spike test - variable load patterns"""
        # Simulate traffic spikes
        spike_factor = random.choice([0.5, 1.0, 2.0, 3.0])  # 50% to 300% normal load

        # Adjust think time based on spike
        think_time = random.uniform(0.5, 2.0) / spike_factor
        time.sleep(min(think_time, 0.1))  # Cap at 100ms

        endpoint = random.choice(["/", "/api/test", "/api/slow"])

        start_time = time.time()
        success = self._api_call("GET", endpoint)
        response_time = (time.time() - start_time) * 1000

        self.results[endpoint].append(
            {
                "response_time": response_time,
                "success": success,
                "user_id": user_id,
                "spike_factor": spike_factor,
                "timestamp": time.time(),
            }
        )

    def _mixed_endpoint_actions(self, user_id: int):
        """Test different endpoints with various HTTP methods"""
        endpoints = [
            ("/", "GET"),
            ("/api/test", "GET"),
            ("/api/slow", "GET"),
        ]

        endpoint, method = random.choice(endpoints)

        start_time = time.time()
        success = self._api_call(method, endpoint)
        response_time = (time.time() - start_time) * 1000

        self.results[f"{method} {endpoint}"].append(
            {
                "response_time": response_time,
                "success": success,
                "user_id": user_id,
                "method": method,
                "timestamp": time.time(),
            }
        )

    def _api_call(self, method, endpoint, data=None):
        """Make API call and return success status"""
        try:
            url = f"{self.base_url}{endpoint}"
            headers = {"Content-Type": "application/json"}

            if method == "GET":
                response = self.session.get(url, headers=headers, timeout=10)
            elif method == "POST":
                response = self.session.post(
                    url, json=data, headers=headers, timeout=10
                )
            else:
                return False

            # Consider 2xx and some 4xx (expected errors) as successful for load testing
            return response.status_code < 500

        except requests.exceptions.RequestException:
            return False

    def _calculate_comprehensive_results(self, scenario):
        """Calculate comprehensive test results with detailed metrics"""
        total_duration = self.end_time - self.start_time
        total_requests = sum(len(requests) for requests in self.results.values())

        # Calculate throughput over time (requests per second)
        if self.metrics["response_times"]:
            time_windows = {}
            for result_list in self.results.values():
                for result in result_list:
                    if "timestamp" in result:
                        window = (
                            int(result["timestamp"] // 10) * 10
                        )  # 10-second windows
                        if window not in time_windows:
                            time_windows[window] = 0
                        time_windows[window] += 1

            throughput_series = []
            for window_start in sorted(time_windows.keys()):
                requests_in_window = time_windows[window_start]
                throughput_series.append(requests_in_window / 10.0)  # req/s

        results = {
            "test_info": {
                "scenario": scenario,
                "test_name": self.test_name,
                "start_time": datetime.fromtimestamp(self.start_time).isoformat(),
                "end_time": datetime.fromtimestamp(self.end_time).isoformat(),
                "duration": total_duration,
                "concurrent_users": self.metrics["concurrent_users"],
            },
            "summary": {
                "total_requests": total_requests,
                "requests_per_second": (
                    total_requests / total_duration if total_duration > 0 else 0
                ),
                "errors": len(self.errors),
                "error_rate": (
                    len(self.errors) / total_requests if total_requests > 0 else 0
                ),
                "avg_response_time": (
                    statistics.mean(self.metrics["response_times"])
                    if self.metrics["response_times"]
                    else 0
                ),
                "median_response_time": (
                    statistics.median(self.metrics["response_times"])
                    if self.metrics["response_times"]
                    else 0
                ),
                "p95_response_time": (
                    statistics.quantiles(self.metrics["response_times"], n=20)[18]
                    if len(self.metrics["response_times"]) >= 20
                    else (
                        max(self.metrics["response_times"])
                        if self.metrics["response_times"]
                        else 0
                    )
                ),
                "p99_response_time": (
                    statistics.quantiles(self.metrics["response_times"], n=100)[98]
                    if len(self.metrics["response_times"]) >= 100
                    else (
                        max(self.metrics["response_times"])
                        if self.metrics["response_times"]
                        else 0
                    )
                ),
            },
            "throughput_analysis": (
                {
                    "peak_throughput": (
                        max(throughput_series)
                        if "throughput_series" in locals() and throughput_series
                        else 0
                    ),
                    "avg_throughput": (
                        statistics.mean(throughput_series)
                        if "throughput_series" in locals() and throughput_series
                        else 0
                    ),
                    "throughput_variance": (
                        statistics.variance(throughput_series)
                        if "throughput_series" in locals()
                        and len(throughput_series) > 1
                        else 0
                    ),
                }
                if "throughput_series" in locals()
                else {}
            ),
            "endpoint_results": {},
            "performance_grades": self._calculate_performance_grades(
                total_requests, total_duration
            ),
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
            }

        return results

    def _calculate_performance_grades(self, total_requests, duration):
        """Calculate performance grades based on test results"""
        if not self.metrics["response_times"]:
            return {
                "overall": "F",
                "throughput": "F",
                "latency": "F",
                "reliability": "F",
            }

        avg_response_time = statistics.mean(self.metrics["response_times"])
        error_rate = len(self.errors) / total_requests if total_requests > 0 else 1
        throughput = total_requests / duration if duration > 0 else 0

        # Latency grade (response time)
        if avg_response_time < 100:
            latency_grade = "A"
        elif avg_response_time < 300:
            latency_grade = "B"
        elif avg_response_time < 500:
            latency_grade = "C"
        elif avg_response_time < 1000:
            latency_grade = "D"
        else:
            latency_grade = "F"

        # Throughput grade
        if throughput > 100:
            throughput_grade = "A"
        elif throughput > 50:
            throughput_grade = "B"
        elif throughput > 20:
            throughput_grade = "C"
        elif throughput > 10:
            throughput_grade = "D"
        else:
            throughput_grade = "F"

        # Reliability grade (error rate)
        if error_rate < 0.01:
            reliability_grade = "A"
        elif error_rate < 0.05:
            reliability_grade = "B"
        elif error_rate < 0.10:
            reliability_grade = "C"
        elif error_rate < 0.20:
            reliability_grade = "D"
        else:
            reliability_grade = "F"

        # Overall grade (weighted average)
        grades = {"A": 4, "B": 3, "C": 2, "D": 1, "F": 0}
        overall_score = (
            grades[latency_grade] * 0.4
            + grades[throughput_grade] * 0.3
            + grades[reliability_grade] * 0.3
        )

        if overall_score >= 3.5:
            overall_grade = "A"
        elif overall_score >= 2.5:
            overall_grade = "B"
        elif overall_score >= 1.5:
            overall_grade = "C"
        elif overall_score >= 0.5:
            overall_grade = "D"
        else:
            overall_grade = "F"

        return {
            "overall": overall_grade,
            "throughput": throughput_grade,
            "latency": latency_grade,
            "reliability": reliability_grade,
            "details": {
                "avg_response_time_ms": avg_response_time,
                "error_rate_percent": error_rate * 100,
                "throughput_req_per_sec": throughput,
            },
        }


def print_comprehensive_results(results):
    """Print comprehensive test results with performance analysis"""
    print("\n" + "=" * 100)
    print("📊 COMPREHENSIVE LOAD TEST RESULTS")
    print("=" * 100)

    # Test info
    info = results["test_info"]
    print(f"🎯 Scenario: {info['scenario'].upper()}")
    print(f"📝 Test: {info['test_name']}")
    print(f"👥 Concurrent Users: {info['concurrent_users']}")
    print(f"⏱️  Duration: {info['duration']:.2f}s")
    print(f"📅 Time: {info['start_time']} - {info['end_time']}")

    # Summary metrics
    summary = results["summary"]
    print("\n📈 SUMMARY METRICS")
    print("-" * 50)
    print(f"📊 Total Requests: {summary['total_requests']}")
    print(f"🚀 Requests/sec: {summary['requests_per_second']:.2f}")
    print(f"❌ Errors: {summary['errors']} ({summary['error_rate']*100:.2f}%)")
    print(f"⚡ Avg Response Time: {summary['avg_response_time']:.2f}ms")
    print(f"📊 Median Response Time: {summary['median_response_time']:.2f}ms")
    print(f"🎯 P95 Response Time: {summary['p95_response_time']:.2f}ms")
    print(f"🎯 P99 Response Time: {summary['p99_response_time']:.2f}ms")

    # Throughput analysis
    if "throughput_analysis" in results and results["throughput_analysis"]:
        ta = results["throughput_analysis"]
        print("\n📈 THROUGHPUT ANALYSIS")
        print("-" * 50)
        print(f"🔺 Peak Throughput: {ta['peak_throughput']:.2f} req/s")
        print(f"📊 Avg Throughput: {ta['avg_throughput']:.2f} req/s")
        print(f"📉 Throughput Variance: {ta['throughput_variance']:.2f}")

    # Performance grades
    grades = results["performance_grades"]
    print("\n🏆 PERFORMANCE GRADES")
    print("-" * 50)
    print(f"🎖️  Overall: {grades['overall']}")
    print(f"🚀 Throughput: {grades['throughput']}")
    print(f"⚡ Latency: {grades['latency']}")
    print(f"🛡️  Reliability: {grades['reliability']}")

    if "details" in grades:
        d = grades["details"]
        print(f"   Response Time: {d['avg_response_time_ms']:.2f}ms")
        print(f"   Error Rate: {d['error_rate_percent']:.2f}%")
        print(f"   Throughput: {d['throughput_req_per_sec']:.2f} req/s")

    # Endpoint breakdown
    print("\n🔍 ENDPOINT PERFORMANCE")
    print("-" * 50)
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
            print(f"   Response Time - P95: {stats['p95_response_time']:.2f}ms")

    print("\n" + "=" * 100)


def run_scenario(scenario_name: str, users: int = None, duration: int = None):
    """Run predefined test scenarios"""
    scenarios = {
        "basic": {"desc": "Basic connectivity test", "users": 1, "duration": 1},
        "light": {
            "desc": "Light load test (10 users, 30s)",
            "users": users or 10,
            "duration": duration or 30,
        },
        "medium": {
            "desc": "Medium load test (30 users, 60s)",
            "users": users or 30,
            "duration": duration or 60,
        },
        "heavy": {
            "desc": "Heavy load test (75 users, 120s)",
            "users": users or 75,
            "duration": duration or 120,
        },
        "stress": {
            "desc": "Stress test (150 users, 180s)",
            "users": users or 150,
            "duration": duration or 180,
        },
        "endurance": {
            "desc": "Endurance test (20 users, 300s)",
            "users": users or 20,
            "duration": duration or 300,
        },
        "spike": {
            "desc": "Spike test (50 users, 120s)",
            "users": users or 50,
            "duration": duration or 120,
        },
        "mixed": {
            "desc": "Mixed endpoints test (25 users, 90s)",
            "users": users or 25,
            "duration": duration or 90,
        },
    }

    if scenario_name not in scenarios:
        print(f"❌ Unknown scenario: {scenario_name}")
        print(f"Available: {', '.join(scenarios.keys())}")
        return

    config = scenarios[scenario_name]
    print(f"🎯 Running scenario: {config['desc']}")

    tester = ComprehensiveLoadTester(
        test_name=f"HelpChain {scenario_name.title()} Test"
    )

    if scenario_name == "basic":
        result = tester.run_basic_test()
        print(f"\n✅ Basic test result: {result}")
    else:
        results = tester.run_load_test(
            scenario_name, config["users"], config["duration"]
        )
        print_comprehensive_results(results)


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
        print("🎯 HelpChain Comprehensive Load Testing")
        print("=" * 50)
        print("Usage:")
        print(
            "  python comprehensive_load_test.py <scenario> [users] [duration_seconds]"
        )
        print("\nScenarios:")
        print("  basic      - Basic connectivity test")
        print("  light      - Light load (10 users, 30s)")
        print("  medium     - Medium load (30 users, 60s)")
        print("  heavy      - Heavy load (75 users, 120s)")
        print("  stress     - Stress test (150 users, 180s)")
        print("  endurance  - Endurance test (20 users, 300s)")
        print("  spike      - Spike test (50 users, 120s)")
        print("  mixed      - Mixed endpoints test (25 users, 90s)")
        print("\nExamples:")
        print("  python comprehensive_load_test.py basic")
        print("  python comprehensive_load_test.py light 15 45")
        print("  python comprehensive_load_test.py stress 200 300")


if __name__ == "__main__":
    main()
