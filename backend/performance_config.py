"""
Performance Configuration за HelpChain Analytics
Този файл съдържа всички настройки за оптимизация на производителността
"""

# from flask_caching import Cache  # Преместен за избягване на circular import
# from flask_compress import Compress  # Преместен за избягване на circular import
import logging
import os


# Performance Configuration
class PerformanceConfig:
    """Configuration за performance optimizations"""

    # Cache Configuration
    CACHE_TYPE = "simple"  # За development - 'redis' за production
    CACHE_DEFAULT_TIMEOUT = 300  # 5 минути default cache

    # Redis Configuration (за production)
    CACHE_REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
    CACHE_REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
    CACHE_REDIS_DB = int(os.environ.get("REDIS_DB", 0))
    CACHE_KEY_PREFIX = "helpchain_analytics_"

    # Compression Configuration
    COMPRESS_MIMETYPES = [
        "text/html",
        "text/css",
        "text/xml",
        "application/json",
        "application/javascript",
        "text/javascript",
    ]
    COMPRESS_LEVEL = 6  # Compression level (1-9)
    COMPRESS_MIN_SIZE = 500  # Minimum size to compress (bytes)

    # Database Performance
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_size": 10,  # Connection pool size
        "pool_recycle": 120,  # Recycle connections after 2 minutes
        "pool_pre_ping": True,  # Verify connections before use
        "max_overflow": 20,  # Allow 20 extra connections if needed
    }

    # Analytics Cache Timeouts (в секунди)
    CACHE_TIMEOUTS = {
        "stats_overview": 300,  # 5 минути за основни статистики
        "daily_data": 1800,  # 30 минути за дневни данни
        "user_behavior": 600,  # 10 минути за user behavior
        "performance_metrics": 180,  # 3 минути за performance данни
        "real_time_data": 30,  # 30 секунди за real-time
        "export_data": 3600,  # 1 час за export данни
    }


def init_performance_optimizations(app):
    """
    Инициализира всички performance optimizations

    Args:
        app: Flask application instance

    Returns:
        dict: Initialized services (cache, compress)
    """

    print("🚀 Initializing Performance Optimizations...")

    # --- Initialize Flask-Caching ---
    from flask_caching import Cache

    # Set default config if not already set
    app.config.setdefault("CACHE_TYPE", PerformanceConfig.CACHE_TYPE)
    app.config.setdefault(
        "CACHE_DEFAULT_TIMEOUT", PerformanceConfig.CACHE_DEFAULT_TIMEOUT
    )
    # For production, you may want to use Redis:
    # app.config["CACHE_TYPE"] = "redis"
    # app.config["CACHE_REDIS_HOST"] = PerformanceConfig.CACHE_REDIS_HOST
    # app.config["CACHE_REDIS_PORT"] = PerformanceConfig.CACHE_REDIS_PORT
    # app.config["CACHE_REDIS_DB"] = PerformanceConfig.CACHE_REDIS_DB
    # app.config["CACHE_KEY_PREFIX"] = PerformanceConfig.CACHE_KEY_PREFIX
    cache = Cache()
    cache.init_app(app)
    # Register cache in extensions for global access
    if not hasattr(app, "extensions"):
        app.extensions = {}
    app.extensions["cache"] = cache
    print("✅ Caching system initialized (Flask-Caching)")

    # --- Initialize Compression (optional, if flask_compress is installed) ---
    compress = None
    try:
        from flask_compress import Compress

        app.config.setdefault(
            "COMPRESS_MIMETYPES", PerformanceConfig.COMPRESS_MIMETYPES
        )
        app.config.setdefault("COMPRESS_LEVEL", PerformanceConfig.COMPRESS_LEVEL)
        app.config.setdefault("COMPRESS_MIN_SIZE", PerformanceConfig.COMPRESS_MIN_SIZE)
        compress = Compress()
        compress.init_app(app)
        print("✅ Response compression initialized (Flask-Compress)")
    except ImportError:
        print("⚠️  Flask-Compress not installed, skipping compression setup.")

    # Configure logging for performance monitoring
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("performance")

    # Performance monitoring middleware
    @app.before_request
    def before_request():
        """Record request start time за performance monitoring"""
        import time

        from flask import g

        g.start_time = time.time()

    @app.after_request
    def after_request(response):
        """Log request performance metrics"""
        import time

        from flask import g, request

        if hasattr(g, "start_time"):
            duration = time.time() - g.start_time
            # Log slow requests (>1 second)
            if duration > 1.0:
                logger.warning(f"Slow request: {request.path} took {duration:.2f}s")
            # Add performance headers
            response.headers["X-Response-Time"] = f"{duration:.3f}"
            response.headers["X-Cache-Status"] = getattr(g, "cache_status", "miss")
        return response

    print("✅ Performance monitoring middleware added")

    return {"cache": cache, "compress": compress, "logger": logger}


# Cache decorators за различни типове данни
def cache_analytics_data(timeout=None, key_prefix="analytics"):
    """
    Decorator за кеширане на analytics данни

    Args:
        timeout: Cache timeout в секунди (default от config)
        key_prefix: Prefix за cache key
    """
    from functools import wraps

    from flask import current_app, g, request

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Опитай да намериш cache инстанцията
            cache = None
            if hasattr(current_app, "extensions") and "cache" in current_app.extensions:
                cache = current_app.extensions["cache"]
            elif hasattr(current_app, "cache"):
                cache = current_app.cache

            if not cache or not hasattr(cache, "get"):
                print("⚠️  Cache not available, executing without caching")
                return f(*args, **kwargs)

            # Създай уникален cache key
            cache_key = f"{key_prefix}_{f.__name__}"
            if request.args:
                params = sorted(request.args.items())
                cache_key += f"_{'_'.join([f'{k}_{v}' for k, v in params])}"

            cache_timeout = timeout or PerformanceConfig.CACHE_TIMEOUTS.get(
                "stats_overview", 300
            )
            # Опитай да вземеш от cache
            result = cache.get(cache_key)
            if result is None:
                result = f(*args, **kwargs)
                cache.set(cache_key, result, timeout=cache_timeout)
                g.cache_status = "miss"
            else:
                g.cache_status = "hit"
            return result

        return decorated_function

    return decorator


# Database optimization utilities
class DatabaseOptimizer:
    """Utilities за database optimization"""

    @staticmethod
    def create_analytics_indexes(db):
        """
        Създава indexes за по-бързи analytics queries

        Args:
            db: SQLAlchemy database instance
        """

        print("📊 Creating database indexes for analytics...")

        try:
            # В SQLAlchemy 2.0+ използваме text() за raw SQL
            from sqlalchemy import text

            # Index за timestamp queries (най-често използван)
            with db.engine.connect() as conn:
                conn.execute(
                    text(
                        """
                    CREATE INDEX IF NOT EXISTS idx_analytics_timestamp
                    ON analytics_event(timestamp DESC)
                """
                    )
                )
                conn.commit()
            print("✅ Created timestamp index")

            # Index за event_type filtering
            with db.engine.connect() as conn:
                conn.execute(
                    text(
                        """
                    CREATE INDEX IF NOT EXISTS idx_analytics_event_type
                    ON analytics_event(event_type)
                """
                    )
                )
                conn.commit()
            print("✅ Created event_type index")

            # Index за category filtering
            with db.engine.connect() as conn:
                conn.execute(
                    text(
                        """
                    CREATE INDEX IF NOT EXISTS idx_analytics_category
                    ON analytics_event(category)
                """
                    )
                )
                conn.commit()
            print("✅ Created category index")

            # Composite index за common filter combinations
            with db.engine.connect() as conn:
                conn.execute(
                    text(
                        """
                    CREATE INDEX IF NOT EXISTS idx_analytics_composite
                    ON analytics_event(timestamp DESC, event_type, category)
                """
                    )
                )
                conn.commit()
            print("✅ Created composite index")

            # Index за user_id queries
            with db.engine.connect() as conn:
                conn.execute(
                    text(
                        """
                    CREATE INDEX IF NOT EXISTS idx_analytics_user_id
                    ON analytics_event(user_id, timestamp DESC)
                """
                    )
                )
                conn.commit()
            print("✅ Created user_id index")

            print("🎉 All database indexes created successfully!")
            return True

        except Exception as e:
            print(f"❌ Error creating indexes: {e}")
            return False

    @staticmethod
    def get_optimized_queries():
        """
        Връща оптимизирани SQL queries за analytics

        Returns:
            dict: Dictionary с оптимизирани queries
        """

        return {
            # Бърза заявка за дневни статистики
            "daily_stats": """
                SELECT
                    DATE(timestamp) as date,
                    event_type,
                    COUNT(*) as count,
                    COUNT(DISTINCT user_id) as unique_users
                FROM analytics_event
                WHERE timestamp >= datetime('now', '-30 days')
                GROUP BY DATE(timestamp), event_type
                ORDER BY date DESC, event_type
            """,
            # Топ страници по посещения
            "top_pages": """
                SELECT
                    JSON_EXTRACT(details, '$.page') as page,
                    COUNT(*) as visits,
                    COUNT(DISTINCT user_id) as unique_visitors
                FROM analytics_event
                WHERE event_type = 'page_view'
                  AND timestamp >= datetime('now', '-7 days')
                  AND JSON_EXTRACT(details, '$.page') IS NOT NULL
                GROUP BY JSON_EXTRACT(details, '$.page')
                ORDER BY visits DESC
                LIMIT 10
            """,
            # User behavior patterns
            "user_sessions": """
                SELECT
                    session_id,
                    COUNT(*) as actions,
                    MIN(timestamp) as session_start,
                    MAX(timestamp) as session_end,
                    (JULIANDAY(MAX(timestamp)) - JULIANDAY(MIN(timestamp))) * 24 * 60 as duration_minutes
                FROM analytics_event
                WHERE timestamp >= datetime('now', '-1 day')
                  AND session_id IS NOT NULL
                GROUP BY session_id
                HAVING actions > 1
                ORDER BY duration_minutes DESC
            """,
            # Performance metrics
            "performance_summary": """
                SELECT
                    DATE(timestamp) as date,
                    AVG(CAST(JSON_EXTRACT(details, '$.load_time') AS REAL)) as avg_load_time,
                    MAX(CAST(JSON_EXTRACT(details, '$.load_time') AS REAL)) as max_load_time,
                    COUNT(*) as total_requests
                FROM analytics_event
                WHERE event_type = 'performance'
                  AND timestamp >= datetime('now', '-7 days')
                  AND JSON_EXTRACT(details, '$.load_time') IS NOT NULL
                GROUP BY DATE(timestamp)
                ORDER BY date DESC
            """,
        }


# Performance monitoring utilities
class PerformanceMonitor:
    """Класс за мониториране на производителността"""

    def __init__(self, app=None):
        self.metrics = {}
        if app:
            self.init_app(app)

    def init_app(self, app):
        """Initialize performance monitoring"""

        @app.before_request
        def start_timer():
            import time

            from flask import g

            g.start_time = time.time()

        @app.after_request
        def record_metrics(response):
            import time

            from flask import g, request

            if hasattr(g, "start_time"):
                duration = time.time() - g.start_time

                # Record metrics
                endpoint = request.endpoint or "unknown"
                if endpoint not in self.metrics:
                    self.metrics[endpoint] = {
                        "total_requests": 0,
                        "total_time": 0,
                        "max_time": 0,
                        "min_time": float("inf"),
                    }

                metrics = self.metrics[endpoint]
                metrics["total_requests"] += 1
                metrics["total_time"] += duration
                metrics["max_time"] = max(metrics["max_time"], duration)
                metrics["min_time"] = min(metrics["min_time"], duration)

                # Add headers
                response.headers["X-Response-Time"] = f"{duration:.3f}s"
                response.headers["X-Request-Count"] = str(metrics["total_requests"])

            return response

    def get_performance_report(self):
        """Get detailed performance report"""

        report = {}
        for endpoint, metrics in self.metrics.items():
            if metrics["total_requests"] > 0:
                avg_time = metrics["total_time"] / metrics["total_requests"]
                report[endpoint] = {
                    "total_requests": metrics["total_requests"],
                    "average_time": round(avg_time, 3),
                    "max_time": round(metrics["max_time"], 3),
                    "min_time": round(metrics["min_time"], 3),
                    "status": (
                        "good"
                        if avg_time < 0.5
                        else "warning" if avg_time < 1.0 else "slow"
                    ),
                }

        return report


if __name__ == "__main__":
    print("🚀 Performance Configuration Module Ready!")
    print("Use init_performance_optimizations(app) to initialize")
