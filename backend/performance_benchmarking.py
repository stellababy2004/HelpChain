import json
import os
import statistics
import time
from datetime import datetime, timedelta
from functools import wraps
from typing import Any

# Try absolute imports first, fall back to relative imports for standalone execution
try:
    from extensions import db
    from models_with_analytics import AnalyticsEvent
except ImportError:
    try:
        from .extensions import db
        from .models_with_analytics import AnalyticsEvent
    except ImportError:
        db = None
        AnalyticsEvent = None


class PerformanceBenchmark:
    """Performance benchmarking utilities for HelpChain"""

    def __init__(self, db_session=None):
        self.db = db_session or db
        self.benchmarks = []
        self.results_file = "performance_benchmarks.json"

    def time_function(self, func_name: str):
        """Decorator to time function execution"""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    execution_time = time.time() - start_time
                    self.record_benchmark(func_name, execution_time, "success")
                    return result
                except Exception as e:
                    execution_time = time.time() - start_time
                    self.record_benchmark(func_name, execution_time, "error", str(e))
                    raise
            return wrapper
        return decorator

    def record_benchmark(self, name: str, duration: float, status: str, error: str = None):
        """Record a benchmark measurement"""
        benchmark = {
            "name": name,
            "duration": duration,
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "error": error
        }
        self.benchmarks.append(benchmark)

        # Keep only last 1000 benchmarks in memory
        if len(self.benchmarks) > 1000:
            self.benchmarks = self.benchmarks[-1000:]

    def get_benchmark_stats(self, name: str = None, hours: int = 24) -> dict[str, Any]:
        """Get benchmark statistics for the specified time period"""
        cutoff_time = datetime.now() - timedelta(hours=hours)

        # Filter benchmarks
        relevant_benchmarks = [
            b for b in self.benchmarks
            if (name is None or b["name"] == name) and
               datetime.fromisoformat(b["timestamp"]) > cutoff_time
        ]

        if not relevant_benchmarks:
            return {
                "count": 0,
                "avg_duration": 0,
                "min_duration": 0,
                "max_duration": 0,
                "success_rate": 0,
                "p95_duration": 0
            }

        durations = [b["duration"] for b in relevant_benchmarks]
        successful = [b for b in relevant_benchmarks if b["status"] == "success"]

        return {
            "count": len(relevant_benchmarks),
            "avg_duration": statistics.mean(durations),
            "min_duration": statistics.mean(durations) if durations else 0,
            "max_duration": max(durations),
            "success_rate": len(successful) / len(relevant_benchmarks),
            "p95_duration": statistics.quantiles(durations, n=20)[18] if len(durations) >= 20 else max(durations)
        }

    def save_benchmarks(self):
        """Save benchmarks to file"""
        try:
            with open(self.results_file, 'w') as f:
                json.dump(self.benchmarks, f, indent=2)
        except Exception as e:
            print(f"Failed to save benchmarks: {e}")

    def load_benchmarks(self):
        """Load benchmarks from file"""
        try:
            if os.path.exists(self.results_file):
                with open(self.results_file) as f:
                    self.benchmarks = json.load(f)
        except Exception as e:
            print(f"Failed to load benchmarks: {e}")

    def clear_benchmarks(self):
        """Clear all benchmark data"""
        self.benchmarks = []
        if os.path.exists(self.results_file):
            os.remove(self.results_file)


class APIResponseTimer:
    """API response time monitoring"""

    def __init__(self, db_session=None):
        self.db = db_session or db
        self.response_times = []

    def record_response_time(self, endpoint: str, method: str, duration: float,
                           status_code: int, user_id: str = None):
        """Record API response time"""
        response_data = {
            "endpoint": endpoint,
            "method": method,
            "duration": duration,
            "status_code": status_code,
            "user_id": user_id,
            "timestamp": datetime.now().isoformat()
        }
        self.response_times.append(response_data)

        # Keep only last 5000 response times in memory
        if len(self.response_times) > 5000:
            self.response_times = self.response_times[-5000:]

        # Store in database if available
        if self.db and AnalyticsEvent:
            try:
                event = AnalyticsEvent(
                    event_type="api_response",
                    event_category="performance",
                    event_action=f"{method}_{endpoint}",
                    user_session=user_id or "anonymous",
                    user_type="api",
                    page_url=endpoint,
                    event_label=json.dumps({
                        "duration": duration,
                        "status_code": status_code,
                        "method": method
                    }),
                    created_at=datetime.now()
                )
                self.db.session.add(event)
                self.db.session.commit()
            except Exception as e:
                print(f"Failed to store API response time: {e}")

    def get_response_stats(self, endpoint: str = None, hours: int = 24) -> dict[str, Any]:
        """Get API response statistics"""
        cutoff_time = datetime.now() - timedelta(hours=hours)

        # Filter response times
        relevant_responses = [
            r for r in self.response_times
            if (endpoint is None or r["endpoint"] == endpoint) and
               datetime.fromisoformat(r["timestamp"]) > cutoff_time
        ]

        if not relevant_responses:
            return {
                "count": 0,
                "avg_duration": 0,
                "min_duration": 0,
                "max_duration": 0,
                "p95_duration": 0,
                "error_rate": 0
            }

        durations = [r["duration"] for r in relevant_responses]
        errors = [r for r in relevant_responses if r["status_code"] >= 400]

        return {
            "count": len(relevant_responses),
            "avg_duration": statistics.mean(durations),
            "min_duration": min(durations),
            "max_duration": max(durations),
            "p95_duration": statistics.quantiles(durations, n=20)[18] if len(durations) >= 20 else max(durations),
            "error_rate": len(errors) / len(relevant_responses)
        }


class DashboardLoadTimer:
    """Dashboard load time measurement utilities"""

    def __init__(self, db_session=None):
        self.db = db_session or db
        self.load_times = []

    def record_dashboard_load(self, dashboard_type: str, load_time: float,
                            component_count: int, data_points: int,
                            user_id: str = None):
        """Record dashboard load time"""
        load_data = {
            "dashboard_type": dashboard_type,
            "load_time": load_time,
            "component_count": component_count,
            "data_points": data_points,
            "user_id": user_id,
            "timestamp": datetime.now().isoformat()
        }
        self.load_times.append(load_data)

        # Keep only last 1000 load times in memory
        if len(self.load_times) > 1000:
            self.load_times = self.load_times[-1000:]

        # Store in database if available
        if self.db and AnalyticsEvent:
            try:
                event = AnalyticsEvent(
                    event_type="dashboard_load",
                    event_category="performance",
                    event_action=f"load_{dashboard_type}",
                    user_session=user_id or "anonymous",
                    user_type="dashboard",
                    page_url=f"/dashboard/{dashboard_type}",
                    event_label=json.dumps({
                        "load_time": load_time,
                        "component_count": component_count,
                        "data_points": data_points
                    }),
                    created_at=datetime.now()
                )
                self.db.session.add(event)
                self.db.session.commit()
            except Exception as e:
                print(f"Failed to store dashboard load time: {e}")

    def get_load_stats(self, dashboard_type: str = None, hours: int = 24) -> dict[str, Any]:
        """Get dashboard load statistics"""
        cutoff_time = datetime.now() - timedelta(hours=hours)

        # Filter load times
        relevant_loads = [
            load for load in self.load_times
            if (dashboard_type is None or load["dashboard_type"] == dashboard_type) and
               datetime.fromisoformat(load["timestamp"]) > cutoff_time
        ]

        if not relevant_loads:
            return {
                "count": 0,
                "avg_load_time": 0,
                "min_load_time": 0,
                "max_load_time": 0,
                "p95_load_time": 0
            }

        load_times = [load["load_time"] for load in relevant_loads]

        return {
            "count": len(relevant_loads),
            "avg_load_time": statistics.mean(load_times),
            "min_load_time": min(load_times),
            "max_load_time": max(load_times),
            "p95_load_time": statistics.quantiles(load_times, n=20)[18] if len(load_times) >= 20 else max(load_times)
        }


class PerformanceMonitor:
    """Comprehensive performance monitoring system"""

    def __init__(self, db_session=None):
        self.db = db_session or db
        self.benchmark = PerformanceBenchmark(db_session)
        self.api_timer = APIResponseTimer(db_session)
        self.dashboard_timer = DashboardLoadTimer(db_session)

    def generate_performance_report(self, hours: int = 24) -> dict[str, Any]:
        """Generate comprehensive performance report"""
        report = {
            "generated_at": datetime.now().isoformat(),
            "time_period_hours": hours,
            "benchmarks": {},
            "api_responses": {},
            "dashboard_loads": {},
            "alerts": []
        }

        # Get benchmark stats for key functions
        key_functions = [
            "detect_anomalies",
            "predict_user_behavior",
            "generate_insights_report",
            "get_analytics_data"
        ]

        for func in key_functions:
            stats = self.benchmark.get_benchmark_stats(func, hours)
            report["benchmarks"][func] = stats

            # Check for performance alerts
            if stats["avg_duration"] > 5.0:  # More than 5 seconds
                report["alerts"].append({
                    "type": "slow_function",
                    "function": func,
                    "avg_duration": stats["avg_duration"],
                    "severity": "high" if stats["avg_duration"] > 10 else "medium"
                })

        # Get API response stats
        api_stats = self.api_timer.get_response_stats(hours=hours)
        report["api_responses"]["all"] = api_stats

        if api_stats["avg_duration"] > 2.0:  # More than 2 seconds
            report["alerts"].append({
                "type": "slow_api",
                "avg_duration": api_stats["avg_duration"],
                "severity": "high" if api_stats["avg_duration"] > 5 else "medium"
            })

        if api_stats["error_rate"] > 0.05:  # More than 5% errors
            report["alerts"].append({
                "type": "high_error_rate",
                "error_rate": api_stats["error_rate"],
                "severity": "high" if api_stats["error_rate"] > 0.1 else "medium"
            })

        # Get dashboard load stats
        dashboard_stats = self.dashboard_timer.get_load_stats(hours=hours)
        report["dashboard_loads"]["all"] = dashboard_stats

        if dashboard_stats["avg_load_time"] > 3.0:  # More than 3 seconds
            report["alerts"].append({
                "type": "slow_dashboard",
                "avg_load_time": dashboard_stats["avg_load_time"],
                "severity": "high" if dashboard_stats["avg_load_time"] > 5 else "medium"
            })

        return report

    def export_report(self, filename: str = None, hours: int = 24):
        """Export performance report to JSON file"""
        if filename is None:
            filename = f"performance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        report = self.generate_performance_report(hours)

        try:
            with open(filename, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"Performance report exported to {filename}")
        except Exception as e:
            print(f"Failed to export report: {e}")


# Global performance monitor instance
performance_monitor = PerformanceMonitor()


def benchmark_function(func_name: str):
    """Decorator to benchmark function performance"""
    return performance_monitor.benchmark.time_function(func_name)


def monitor_api_response(endpoint: str, method: str):
    """Decorator to monitor API response times"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                # Extract user_id from kwargs or args if available
                user_id = kwargs.get('user_id') or getattr(args[0] if args else None, 'user_id', None)

                result = func(*args, **kwargs)
                execution_time = time.time() - start_time

                # Get status code from result if it's a Flask response
                status_code = getattr(result, 'status_code', 200) if hasattr(result, '__dict__') else 200

                performance_monitor.api_timer.record_response_time(
                    endpoint, method, execution_time, status_code, user_id
                )
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                performance_monitor.api_timer.record_response_time(
                    endpoint, method, execution_time, 500, None
                )
                raise
        return wrapper
    return decorator


def monitor_dashboard_load(dashboard_type: str):
    """Decorator to monitor dashboard load times"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                # Extract user_id from kwargs or args if available
                user_id = kwargs.get('user_id') or getattr(args[0] if args else None, 'user_id', None)

                result = func(*args, **kwargs)
                load_time = time.time() - start_time

                # Estimate component count and data points (this would be more sophisticated in real implementation)
                component_count = getattr(result, 'component_count', 10) if hasattr(result, '__dict__') else 10
                data_points = getattr(result, 'data_points', 100) if hasattr(result, '__dict__') else 100

                performance_monitor.dashboard_timer.record_dashboard_load(
                    dashboard_type, load_time, component_count, data_points, user_id
                )
                return result
            except Exception as e:
                load_time = time.time() - start_time
                performance_monitor.dashboard_timer.record_dashboard_load(
                    dashboard_type, load_time, 0, 0, user_id
                )
                raise
        return wrapper
    return decorator