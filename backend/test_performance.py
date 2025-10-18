"""
Performance Testing Script за HelpChain Analytics
Този скрипт тества производителността на оптимизираното приложение
"""

import statistics
import time
from datetime import datetime

import requests


class PerformanceTester:
    """Class за тестване на производителността"""

    def __init__(self, base_url="http://localhost:5000"):
        self.base_url = base_url
        self.results = {}

    def test_endpoint(self, endpoint, params=None, iterations=5):
        """
        Тества производителността на даден endpoint

        Args:
            endpoint: URL endpoint за тестване
            params: Query параметри
            iterations: Брой повторения за по-точни резултати
        """

        print(f"\n🧪 Testing {endpoint}...")

        url = f"{self.base_url}{endpoint}"
        times = []
        cache_hits = 0
        errors = 0

        for i in range(iterations):
            try:
                start_time = time.time()
                response = requests.get(url, params=params, timeout=10)
                end_time = time.time()

                duration = end_time - start_time
                times.append(duration)

                # Check cache status
                if response.headers.get("X-Cache-Status") == "hit":
                    cache_hits += 1

                print(
                    f"  Request {i+1}: {duration:.3f}s (Status: {response.status_code}, Cache: {response.headers.get('X-Cache-Status', 'unknown')})"
                )

                # Small delay между requests
                time.sleep(0.1)

            except Exception as e:
                errors += 1
                print(f"  Request {i+1}: ERROR - {e}")

        if times:
            avg_time = statistics.mean(times)
            min_time = min(times)
            max_time = max(times)

            self.results[endpoint] = {
                "avg_response_time": avg_time,
                "min_response_time": min_time,
                "max_response_time": max_time,
                "cache_hit_rate": (cache_hits / iterations) * 100,
                "error_rate": (errors / iterations) * 100,
                "total_requests": iterations,
                "successful_requests": len(times),
            }

            print("  📊 Results:")
            print(f"     Average: {avg_time:.3f}s")
            print(f"     Min: {min_time:.3f}s")
            print(f"     Max: {max_time:.3f}s")
            print(f"     Cache hit rate: {(cache_hits/iterations)*100:.1f}%")
            print(f"     Error rate: {(errors/iterations)*100:.1f}%")

            # Performance rating
            if avg_time < 0.2:
                rating = "🟢 EXCELLENT"
            elif avg_time < 0.5:
                rating = "🟡 GOOD"
            elif avg_time < 1.0:
                rating = "🟠 OK"
            else:
                rating = "🔴 SLOW"

            print(f"     Performance: {rating}")

        return self.results.get(endpoint, {})

    def test_cache_effectiveness(self):
        """Тества ефективността на caching системата"""

        print("\n🔄 Testing Cache Effectiveness...")

        # First request (should be cache miss)
        print("First request (cache miss expected):")
        result1 = self.test_endpoint("/api/analytics-data", iterations=1)

        # Wait a moment
        time.sleep(1)

        # Second request (should be cache hit)
        print("Second request (cache hit expected):")
        result2 = self.test_endpoint("/api/analytics-data", iterations=1)

        # Compare performance
        if result1 and result2:
            improvement = (
                (result1["avg_response_time"] - result2["avg_response_time"])
                / result1["avg_response_time"]
            ) * 100
            print(f"\n📈 Cache Performance Improvement: {improvement:.1f}%")

            if improvement > 50:
                print("🎉 Excellent cache performance!")
            elif improvement > 20:
                print("✅ Good cache performance!")
            else:
                print("⚠️  Limited cache benefit - consider optimization")

    def test_concurrent_requests(
        self, endpoint="/api/analytics-data", concurrent_users=10
    ):
        """Тества производителността при concurrent requests"""

        print(f"\n👥 Testing Concurrent Performance ({concurrent_users} users)...")

        import queue
        import threading

        results_queue = queue.Queue()

        def make_request():
            try:
                start_time = time.time()
                response = requests.get(f"{self.base_url}{endpoint}", timeout=10)
                end_time = time.time()

                results_queue.put(
                    {
                        "duration": end_time - start_time,
                        "status": response.status_code,
                        "cache_status": response.headers.get(
                            "X-Cache-Status", "unknown"
                        ),
                    }
                )
            except Exception as e:
                results_queue.put({"duration": None, "error": str(e)})

        # Start concurrent requests
        threads = []
        start_time = time.time()

        for _ in range(concurrent_users):
            thread = threading.Thread(target=make_request)
            thread.start()
            threads.append(thread)

        # Wait за всички threads
        for thread in threads:
            thread.join()

        total_time = time.time() - start_time

        # Collect results
        durations = []
        errors = 0
        cache_hits = 0

        while not results_queue.empty():
            result = results_queue.get()
            if "error" in result:
                errors += 1
            else:
                durations.append(result["duration"])
                if result.get("cache_status") == "hit":
                    cache_hits += 1

        if durations:
            avg_duration = statistics.mean(durations)
            max_duration = max(durations)

            print(f"  Total time: {total_time:.3f}s")
            print(f"  Average response time: {avg_duration:.3f}s")
            print(f"  Slowest response: {max_duration:.3f}s")
            print(f"  Successful requests: {len(durations)}/{concurrent_users}")
            print(f"  Cache hit rate: {(cache_hits/len(durations))*100:.1f}%")
            print(f"  Error rate: {(errors/concurrent_users)*100:.1f}%")

            # Throughput calculation
            throughput = concurrent_users / total_time
            print(f"  Throughput: {throughput:.1f} requests/second")

    def generate_performance_report(self):
        """Генерира подробен performance report"""

        print("\n📋 PERFORMANCE REPORT")
        print("=" * 50)
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Base URL: {self.base_url}")

        if not self.results:
            print("No test results available.")
            return

        for endpoint, metrics in self.results.items():
            print(f"\n🔗 Endpoint: {endpoint}")
            print(f"   Average Response Time: {metrics['avg_response_time']:.3f}s")
            print(
                f"   Response Time Range: {metrics['min_response_time']:.3f}s - {metrics['max_response_time']:.3f}s"
            )
            print(f"   Cache Hit Rate: {metrics['cache_hit_rate']:.1f}%")
            print(f"   Error Rate: {metrics['error_rate']:.1f}%")
            print(f"   Total Requests: {metrics['total_requests']}")

            # Recommendations
            avg_time = metrics["avg_response_time"]
            if avg_time > 1.0:
                print("   ⚠️  RECOMMENDATION: Optimize - response time too slow")
            elif avg_time > 0.5:
                print("   💡 SUGGESTION: Consider further optimization")
            else:
                print("   ✅ GOOD: Response time within acceptable range")

            if metrics["cache_hit_rate"] < 30:
                print("   ⚠️  RECOMMENDATION: Improve caching strategy")
            elif metrics["cache_hit_rate"] > 70:
                print("   ✅ EXCELLENT: High cache efficiency")

        # Overall rating
        avg_times = [m["avg_response_time"] for m in self.results.values()]
        if avg_times:
            overall_avg = statistics.mean(avg_times)

            print("\n🏆 OVERALL PERFORMANCE RATING:")
            if overall_avg < 0.3:
                print(f"   🟢 EXCELLENT (Avg: {overall_avg:.3f}s)")
            elif overall_avg < 0.6:
                print(f"   🟡 GOOD (Avg: {overall_avg:.3f}s)")
            elif overall_avg < 1.0:
                print(f"   🟠 FAIR (Avg: {overall_avg:.3f}s)")
            else:
                print(f"   🔴 NEEDS IMPROVEMENT (Avg: {overall_avg:.3f}s)")


def run_comprehensive_test():
    """Изпълнява comprehensive performance test"""

    print("🚀 Starting Comprehensive Performance Test")
    print("=" * 60)

    tester = PerformanceTester()

    # Test основни endpoints
    endpoints_to_test = [
        ("/api/analytics-data", {}),
        ("/api/analytics-data", {"days": 7}),
        ("/api/analytics-data", {"days": 30, "event_type": "page_view"}),
        ("/admin/analytics", {}),
    ]

    for endpoint, params in endpoints_to_test:
        tester.test_endpoint(endpoint, params=params, iterations=3)

    # Test cache effectiveness
    tester.test_cache_effectiveness()

    # Test concurrent performance
    tester.test_concurrent_requests(concurrent_users=5)

    # Generate final report
    tester.generate_performance_report()


if __name__ == "__main__":
    print("🧪 HelpChain Performance Tester")
    print("Make sure the Flask app is running on http://localhost:5000")

    try:
        # Quick connectivity test
        response = requests.get("http://localhost:5000/api/analytics-data", timeout=5)
        print(f"✅ Server connectivity OK (Status: {response.status_code})")

        # Run comprehensive test
        run_comprehensive_test()

    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server. Make sure Flask app is running!")
    except Exception as e:
        print(f"❌ Error during testing: {e}")
