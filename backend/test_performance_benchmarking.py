#!/usr/bin/env python
"""
Performance benchmarking tests for HelpChain application
Tests response times, database query performance, and system load
"""

import statistics
import time
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest


class TestPerformanceBenchmarking:
    """Performance benchmarking test suite"""

    def test_api_response_times(
        self, client, authenticated_volunteer_client, authenticated_admin_client
    ):
        """Benchmark API endpoint response times"""
        endpoints = [
            ("/api/volunteer/dashboard", authenticated_volunteer_client),
            ("/api/admin/dashboard", authenticated_admin_client),
            ("/api/volunteer/tasks", authenticated_volunteer_client),
            ("/api/user/profile", authenticated_volunteer_client),
            ("/api/ai/status", authenticated_admin_client),
        ]

        results = {}

        for endpoint, test_client in endpoints:
            response_times = []

            # Make 5 requests to get average
            for _ in range(5):
                start_time = time.time()
                response = test_client.get(endpoint)
                end_time = time.time()

                if response.status_code in [200, 404]:  # Acceptable responses
                    response_times.append(
                        (end_time - start_time) * 1000
                    )  # Convert to milliseconds

            if response_times:
                results[endpoint] = {
                    "avg_response_time": statistics.mean(response_times),
                    "min_response_time": min(response_times),
                    "max_response_time": max(response_times),
                    "p95_response_time": (
                        statistics.quantiles(response_times, n=20)[18]
                        if len(response_times) >= 20
                        else max(response_times)
                    ),
                    "success_rate": len(response_times) / 5.0,
                }

                # Assert reasonable performance (under 2 seconds for API calls)
                assert (
                    results[endpoint]["avg_response_time"] < 2000
                ), f"{endpoint} too slow: {results[endpoint]['avg_response_time']}ms"

        # Log results for analysis
        print(f"API Performance Results: {results}")
        assert len(results) > 0, "No endpoints were successfully tested"

    def test_database_query_performance(self, db_session):
        """Benchmark database query performance"""
        from models import AdminUser, HelpRequest, Volunteer

        # Test basic SELECT queries
        query_times = {}

        # Volunteer count query
        start_time = time.time()
        volunteer_count = db_session.query(Volunteer).count()
        end_time = time.time()
        query_times["volunteer_count"] = (end_time - start_time) * 1000

        # Help request query with filtering
        start_time = time.time()
        recent_requests = (
            db_session.query(HelpRequest)
            .filter(HelpRequest.created_at >= datetime.utcnow() - timedelta(days=30))
            .limit(100)
            .all()
        )
        end_time = time.time()
        query_times["recent_requests"] = (end_time - start_time) * 1000

        # Admin user query
        start_time = time.time()
        admin_users = db_session.query(AdminUser).all()
        end_time = time.time()
        query_times["admin_users"] = (end_time - start_time) * 1000

        # Complex join query (if analytics tables exist)
        try:
            from models_with_analytics import AnalyticsEvent

            start_time = time.time()
            analytics_data = db_session.query(AnalyticsEvent).limit(1000).all()
            end_time = time.time()
            query_times["analytics_events"] = (end_time - start_time) * 1000
        except ImportError:
            query_times["analytics_events"] = 0

        # Assert reasonable query performance (under 500ms for most queries)
        for query_name, query_time in query_times.items():
            if query_time > 0:  # Skip unavailable queries
                assert query_time < 500, f"Query {query_name} too slow: {query_time}ms"

        print(f"Database Query Performance: {query_times}")

    def test_memory_usage_simulation(self, client, authenticated_volunteer_client):
        """Simulate memory usage under load"""
        try:
            import os

            import psutil  # type: ignore

            # Get initial memory usage
            process = psutil.Process(os.getpid())
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB

            # Make multiple API calls to simulate load
            for i in range(20):
                response = authenticated_volunteer_client.get(
                    "/api/volunteer/dashboard"
                )
                assert response.status_code in [200, 404]

            # Check memory usage after load
            final_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = final_memory - initial_memory

            # Assert reasonable memory usage (under 50MB increase)
            assert (
                memory_increase < 50
            ), f"Memory usage increased too much: {memory_increase}MB"

            print(
                f"Memory Usage - Initial: {initial_memory:.2f}MB, Final: {final_memory:.2f}MB, Increase: {memory_increase:.2f}MB"
            )
        except ImportError:
            pytest.skip("psutil not available for memory testing")

    def test_concurrent_requests_simulation(
        self, client, authenticated_volunteer_client
    ):
        """Test performance under concurrent requests"""
        import queue
        import threading

        results_queue = queue.Queue()
        num_threads = 5
        requests_per_thread = 5

        def make_requests(thread_id):
            thread_results = []
            for i in range(requests_per_thread):
                start_time = time.time()
                try:
                    response = authenticated_volunteer_client.get(
                        "/api/volunteer/dashboard"
                    )
                    end_time = time.time()
                    thread_results.append(
                        {
                            "status_code": response.status_code,
                            "response_time": (end_time - start_time) * 1000,
                        }
                    )
                except Exception as e:
                    thread_results.append(
                        {
                            "error": str(e),
                            "response_time": (time.time() - start_time) * 1000,
                        }
                    )
            results_queue.put(thread_results)

        # Start concurrent threads
        threads = []
        start_time = time.time()

        for thread_id in range(num_threads):
            thread = threading.Thread(target=make_requests, args=(thread_id,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        total_time = (time.time() - start_time) * 1000

        # Collect results
        all_results = []
        while not results_queue.empty():
            all_results.extend(results_queue.get())

        # Analyze results
        successful_requests = [
            r
            for r in all_results
            if "status_code" in r and r["status_code"] in [200, 404]
        ]
        response_times = [r["response_time"] for r in successful_requests]

        if response_times:
            avg_response_time = statistics.mean(response_times)
            max_response_time = max(response_times)
            success_rate = len(successful_requests) / len(all_results)

            # Assert reasonable concurrent performance
            assert (
                avg_response_time < 3000
            ), f"Average response time too slow under concurrency: {avg_response_time}ms"
            assert (
                success_rate > 0.8
            ), f"Success rate too low under concurrency: {success_rate}"
            assert (
                max_response_time < 10000
            ), f"Max response time too high: {max_response_time}ms"

            print(
                f"Concurrent Performance - Total time: {total_time:.2f}ms, "
                f"Avg response: {avg_response_time:.2f}ms, "
                f"Success rate: {success_rate:.2%}"
            )

    def test_cache_performance(self, client, authenticated_volunteer_client):
        """Test caching performance improvements"""
        # Make initial request (should cache)
        start_time = time.time()
        response1 = authenticated_volunteer_client.get("/api/volunteer/dashboard")
        first_request_time = (time.time() - start_time) * 1000

        # Make second request (should use cache)
        start_time = time.time()
        response2 = authenticated_volunteer_client.get("/api/volunteer/dashboard")
        second_request_time = (time.time() - start_time) * 1000

        # Cache should improve performance (second request should be faster)
        if response1.status_code == response2.status_code == 200:
            improvement = first_request_time - second_request_time
            improvement_percentage = (
                (improvement / first_request_time) * 100
                if first_request_time > 0
                else 0
            )

            # Log cache performance (don't assert as caching may not be implemented for all endpoints)
            print(
                f"Cache Performance - First: {first_request_time:.2f}ms, "
                f"Second: {second_request_time:.2f}ms, "
                f"Improvement: {improvement:.2f}ms ({improvement_percentage:.1f}%)"
            )

    def test_database_connection_pooling(self, db_session):
        """Test database connection pooling efficiency"""
        from models import Volunteer

        connection_times = []

        for i in range(10):
            start_time = time.time()
            # Simple query to test connection
            result = db_session.query(Volunteer).count()
            end_time = time.time()
            connection_times.append((end_time - start_time) * 1000)

        avg_connection_time = statistics.mean(connection_times)

        # Assert reasonable connection times (under 50ms)
        assert (
            avg_connection_time < 50
        ), f"Database connections too slow: {avg_connection_time}ms"

        print(
            f"Database Connection Performance - Avg time: {avg_connection_time:.2f}ms"
        )

    def test_static_asset_performance(self, client):
        """Test static asset serving performance"""
        # Test CSS/JS asset serving if available
        asset_endpoints = [
            "/static/styles.css",
            "/static/bootstrap.min.css",
            "/static/jquery.min.js",
        ]

        for asset_url in asset_endpoints:
            start_time = time.time()
            response = client.get(asset_url)
            end_time = time.time()

            if response.status_code == 200:
                load_time = (end_time - start_time) * 1000
                # Assert reasonable asset loading (under 500ms)
                assert (
                    load_time < 500
                ), f"Asset {asset_url} loads too slowly: {load_time}ms"
                print(f"Asset Performance - {asset_url}: {load_time:.2f}ms")

    def test_error_handling_performance(self, client):
        """Test error handling doesn't significantly impact performance"""
        # Test 404 errors
        error_endpoints = [
            "/api/nonexistent",
            "/invalid/path",
            "/api/volunteer/nonexistent",
        ]

        for endpoint in error_endpoints:
            start_time = time.time()
            response = client.get(endpoint)
            end_time = time.time()

            error_time = (end_time - start_time) * 1000

            # Error responses should still be reasonably fast (under 1 second)
            assert (
                error_time < 1000
            ), f"Error handling too slow for {endpoint}: {error_time}ms"

        print("Error handling performance test completed")

    def test_json_serialization_performance(self, authenticated_volunteer_client):
        """Test JSON serialization performance for API responses"""
        import json

        response = authenticated_volunteer_client.get("/api/volunteer/dashboard")

        if response.status_code == 200:
            # Test JSON parsing performance
            json_data = response.get_data(as_text=True)

            parse_times = []
            for _ in range(10):
                start_time = time.time()
                parsed_data = json.loads(json_data)
                end_time = time.time()
                parse_times.append((end_time - start_time) * 1000)

            avg_parse_time = statistics.mean(parse_times)

            # Assert reasonable JSON parsing performance (under 10ms)
            assert avg_parse_time < 10, f"JSON parsing too slow: {avg_parse_time}ms"

            print(
                f"JSON Serialization Performance - Parse time: {avg_parse_time:.2f}ms"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
