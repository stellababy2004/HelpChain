"""
Simple Manual Cache System за HelpChain Analytics
Прост, ефективен caching механизъм без dependencies
"""

import time
from functools import wraps
import json
import hashlib


class SimpleCache:
    """Simple in-memory cache implementation"""

    def __init__(self):
        self._cache = {}
        self._timeouts = {}
        print("🔄 SimpleCache initialized")

    def _cleanup_expired(self):
        """Премахва expired entries"""
        current_time = time.time()
        expired_keys = [
            key for key, timeout in self._timeouts.items() if timeout < current_time
        ]

        for key in expired_keys:
            if key in self._cache:
                del self._cache[key]
            del self._timeouts[key]

    def get(self, key):
        """Взема стойност от cache"""
        self._cleanup_expired()
        return self._cache.get(key)

    def set(self, key, value, timeout=300):
        """Записва стойност в cache"""
        self._cache[key] = value
        self._timeouts[key] = time.time() + timeout

        # Ограничи cache размера (max 1000 entries)
        if len(self._cache) > 1000:
            # Премахни най-старите 20% entries
            oldest_keys = sorted(self._timeouts.items(), key=lambda x: x[1])[:200]

            for key, _ in oldest_keys:
                if key in self._cache:
                    del self._cache[key]
                del self._timeouts[key]

    def delete(self, key):
        """Изтрива entry от cache"""
        if key in self._cache:
            del self._cache[key]
        if key in self._timeouts:
            del self._timeouts[key]

    def clear(self):
        """Изчиства целия cache"""
        self._cache.clear()
        self._timeouts.clear()

    def stats(self):
        """Връща cache статистики"""
        self._cleanup_expired()
        return {
            "total_entries": len(self._cache),
            "memory_usage_mb": len(str(self._cache)) / (1024 * 1024),
            "oldest_entry": min(self._timeouts.values()) if self._timeouts else None,
            "newest_entry": max(self._timeouts.values()) if self._timeouts else None,
        }


# Global cache instance
_global_cache = SimpleCache()


def get_cache_key(func_name, args=None, kwargs=None):
    """Генерира уникален cache key"""

    # Базов key от function name
    key_parts = [func_name]

    # Добави args ако има
    if args:
        key_parts.append(f"args_{hash(str(args))}")

    # Добави kwargs ако има
    if kwargs:
        # Сортирай kwargs за consistent key
        sorted_kwargs = sorted(kwargs.items())
        kwargs_str = json.dumps(sorted_kwargs, sort_keys=True, default=str)
        kwargs_hash = hashlib.sha256(kwargs_str.encode()).hexdigest()[:10]
        key_parts.append(f"kwargs_{kwargs_hash}")

    return "_".join(key_parts)


def simple_cache(timeout=300, key_prefix="cache"):
    """
    Simple cache decorator

    Args:
        timeout: Cache timeout в секунди (default: 5 минути)
        key_prefix: Prefix за cache key
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Генерирай cache key
            cache_key = f"{key_prefix}_{get_cache_key(func.__name__, args, kwargs)}"

            # Опитай да вземеш от cache
            cached_result = _global_cache.get(cache_key)

            if cached_result is not None:
                print(f"✅ Cache HIT: {func.__name__} (key: {cache_key[:50]}...)")
                return cached_result

            # Cache miss - изчисли резултата
            print(f"❌ Cache MISS: {func.__name__} (key: {cache_key[:50]}...)")
            result = func(*args, **kwargs)

            # Запази в cache
            _global_cache.set(cache_key, result, timeout)
            print(f"💾 Cached result for {func.__name__} (timeout: {timeout}s)")

            return result

        return wrapper

    return decorator


# Request-based caching (за Flask routes)
def cache_request_data(timeout=300, key_prefix="request"):
    """
    Cache decorator за Flask request data
    Автоматично включва request параметри в cache key
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                from flask import request, g

                # Генерирай cache key с request параметри
                request_params = dict(request.args)
                cache_key = (
                    f"{key_prefix}_{get_cache_key(func.__name__, args, request_params)}"
                )

                # Опитай да вземеш от cache
                cached_result = _global_cache.get(cache_key)

                if cached_result is not None:
                    print(f"✅ Request Cache HIT: {func.__name__}")
                    g.cache_status = "hit"
                    return cached_result

                # Cache miss
                print(f"❌ Request Cache MISS: {func.__name__}")
                g.cache_status = "miss"
                result = func(*args, **kwargs)

                # Запази в cache
                _global_cache.set(cache_key, result, timeout)
                print(f"💾 Cached request result for {func.__name__}")

                return result

            except Exception as e:
                print(f"⚠️  Cache error: {e}, executing without cache")
                # извикване за side-effects, без да създаваме unused var
                _ = func(*args, **kwargs)

        return wrapper

    return decorator


# Cache management functions
def cache_stats():
    """Връща cache статистики"""
    return _global_cache.stats()


def clear_cache():
    """Изчиства cache"""
    _global_cache.clear()
    print("🧹 Cache cleared")


def warm_cache(warm_functions):
    """
    Предварително зарежда cache с често използвани данни

    Args:
        warm_functions: List от функции за изпълнение
    """
    print("🔥 Starting cache warming...")

    for func_info in warm_functions:
        try:
            func = func_info["function"]
            args = func_info.get("args", ())
            kwargs = func_info.get("kwargs", {})

            print(f"  Warming {func.__name__}...")
            start_time = time.time()
            _ = func(*args, **kwargs)
            duration = time.time() - start_time

            print(f"  ✅ {func.__name__} warmed in {duration:.3f}s")

        except Exception as e:
            print(
                f"  ❌ Failed to warm {func_info.get('function', {}).get('__name__', 'unknown')}: {e}"
            )

    print("🔥 Cache warming complete!")


# Performance monitoring
class CachePerformanceMonitor:
    """Мониторира cache performance"""

    def __init__(self):
        self.hits = 0
        self.misses = 0
        self.start_time = time.time()

    def record_hit(self):
        self.hits += 1

    def record_miss(self):
        self.misses += 1

    def get_hit_rate(self):
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0

    def get_report(self):
        runtime = time.time() - self.start_time
        total_requests = self.hits + self.misses

        return {
            "hit_rate": self.get_hit_rate(),
            "total_hits": self.hits,
            "total_misses": self.misses,
            "total_requests": total_requests,
            "runtime_minutes": runtime / 60,
            "requests_per_minute": (
                total_requests / (runtime / 60) if runtime > 0 else 0
            ),
        }


# Global performance monitor
_perf_monitor = CachePerformanceMonitor()


def get_cache_performance():
    """Връща cache performance metrics"""
    return _perf_monitor.get_report()


# Global cache instance for easy import
cache_instance = SimpleCache()

if __name__ == "__main__":
    # Test the cache system
    print("🧪 Testing SimpleCache...")

    @simple_cache(timeout=5, key_prefix="test")
    def expensive_calculation(x, y):
        """Simulate expensive calculation"""
        time.sleep(1)  # Simulate work
        return x * y + (x**2)

    # Test cache functionality
    print("\n1️⃣ First call (should be slow):")
    start = time.time()
    result1 = expensive_calculation(10, 20)
    print(f"Result: {result1}, Time: {time.time() - start:.3f}s")

    print("\n2️⃣ Second call (should be fast - cached):")
    start = time.time()
    result2 = expensive_calculation(10, 20)
    print(f"Result: {result2}, Time: {time.time() - start:.3f}s")

    print(f"\n📊 Cache Stats: {cache_stats()}")
    print(f"📈 Performance: {get_cache_performance()}")

    print("\n✅ SimpleCache test complete!")
