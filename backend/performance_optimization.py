"""
Performance Optimization для Analytics System
Caching, Database optimization и API improvements
"""

# from flask_caching import Cache  # Преместен вътре в класа за избягване на circular import
import json
import os
import socket
from datetime import datetime
from functools import wraps


class AnalyticsCache:
    def __init__(self, app=None):
        from flask_caching import (
            Cache,
        )  # Локален import за избягване на circular import

        self.cache = None
        if app:
            self.init_app(app)

    def init_app(self, app):
        """Initialize the cache with the Flask app"""
        from flask_caching import Cache  # Import here for init_app method

        try:
            # Configure cache with Redis URL
            cache_config = PERFORMANCE_CONFIG.copy()
            app.config.update(cache_config)
            self.cache = Cache(app)
            print("✅ Cache initialized successfully")

        except Exception as e:
            # If anything fails, fallback to simple cache
            print(f"⚠️  Cache initialization failed ({e}), using simple fallback")
            app.config["CACHE_TYPE"] = "simple"
            app.config["CACHE_DEFAULT_TIMEOUT"] = 300
            self.cache = Cache(app)

    def cached_analytics_data(self, timeout=None):
        """Decorator за caching на analytics данни"""

        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                # Check if cache is initialized
                if self.cache is None:
                    print("⚠️  Cache not initialized, calling function directly")
                    return f(*args, **kwargs)

                # Създай unique cache key от параметрите
                cache_key = (
                    f"analytics_{f.__name__}_{hash(str(sorted(kwargs.items())))}"
                )

                # Провери дали има cached версия
                result = self.cache.get(cache_key)
                if result is None:
                    result = f(*args, **kwargs)
                    cache_timeout = (
                        timeout if timeout is not None else self.cache.default_timeout
                    )
                    self.cache.set(cache_key, result, timeout=cache_timeout)

                return result

            return decorated_function

        return decorator

    def invalidate_analytics_cache(self):
        """Изчисти всички analytics cache entries"""
        # За simple cache - изчисти всичко
        self.cache.clear()


class DatabaseOptimizer:
    """Database optimization utilities"""

    @staticmethod
    def create_analytics_indexes(db):
        """Създай indexes за по-бърз analytics access"""
        try:
            from sqlalchemy import text

            # Index за timestamp queries - use created_at column
            db.session.execute(
                text(
                    """
                CREATE INDEX IF NOT EXISTS idx_analytics_timestamp
                ON analytics_events(created_at DESC)
            """
                )
            )

            # Index за event_type filtering
            db.session.execute(
                text(
                    """
                CREATE INDEX IF NOT EXISTS idx_analytics_event_type
                ON analytics_events(event_type)
            """
                )
            )

            # Index за category filtering
            db.session.execute(
                text(
                    """
                CREATE INDEX IF NOT EXISTS idx_analytics_category
                ON analytics_events(event_category)
            """
                )
            )

            # Composite index за common filters
            db.session.execute(
                text(
                    """
                CREATE INDEX IF NOT EXISTS idx_analytics_composite
                ON analytics_events(created_at DESC, event_type, event_category)
            """
                )
            )

            # Additional indexes for user_behaviors table
            db.session.execute(
                text(
                    """
                CREATE INDEX IF NOT EXISTS idx_user_behaviors_session_start
                ON user_behaviors(session_start DESC)
            """
                )
            )

            # Index for performance_metrics table
            db.session.execute(
                text(
                    """
                CREATE INDEX IF NOT EXISTS idx_performance_metrics_timestamp
                ON performance_metrics(created_at DESC)
            """
                )
            )

            # Index for chatbot_conversations table
            db.session.execute(
                text(
                    """
                CREATE INDEX IF NOT EXISTS idx_chatbot_conversations_timestamp
                ON chatbot_conversations(created_at DESC)
            """
                )
            )

            db.session.commit()
            print("✅ Analytics database indexes created successfully")
            return True

        except Exception as e:
            db.session.rollback()
            print(f"❌ Error creating indexes: {e}")
            return False

    @staticmethod
    def get_optimized_analytics_queries():
        """Get optimized analytics queries using proper SQLAlchemy syntax"""
        return {
            "events_by_day": """
                SELECT DATE(created_at) as date,
                       COUNT(*) as count,
                       event_type
                FROM analytics_events
                WHERE created_at >= :start_date AND created_at <= :end_date
                GROUP BY DATE(created_at), event_type
                ORDER BY date DESC
            """,
            "top_pages": """
                SELECT page_url as page,
                       COUNT(*) as visits
                FROM analytics_events
                WHERE event_type = 'page_view'
                  AND created_at >= :start_date AND created_at <= :end_date
                GROUP BY page_url
                ORDER BY visits DESC
                LIMIT 10
            """,
            "user_behavior_summary": """
                SELECT session_id,
                       COUNT(*) as actions,
                       MIN(created_at) as session_start,
                       MAX(created_at) as session_end
                FROM analytics_events
                WHERE created_at >= :start_date AND created_at <= :end_date
                GROUP BY session_id
                HAVING actions > 1
                ORDER BY actions DESC
                LIMIT 100
            """,
            "performance_by_endpoint": """
                SELECT endpoint,
                       AVG(metric_value) as avg_time,
                       COUNT(*) as request_count
                FROM performance_metrics
                WHERE metric_type = 'response_time'
                  AND created_at >= :start_date AND created_at <= :end_date
                  AND endpoint IS NOT NULL
                GROUP BY endpoint
                ORDER BY avg_time DESC
                LIMIT 10
            """,
            "chatbot_conversations_summary": """
                SELECT response_type,
                       COUNT(*) as count
                FROM chatbot_conversations
                WHERE created_at >= :start_date AND created_at <= :end_date
                GROUP BY response_type
            """,
            "chatbot_ai_stats": """
                SELECT COUNT(*) as total_ai_responses,
                       AVG(ai_confidence) as avg_confidence,
                       AVG(processing_time) as avg_processing_time,
                       SUM(ai_tokens_used) as total_tokens
                FROM chatbot_conversations
                WHERE response_type = 'ai'
                  AND created_at >= :start_date AND created_at <= :end_date
            """,
            "chatbot_ratings": """
                SELECT COUNT(*) as rated_conversations,
                       AVG(user_rating) as avg_rating
                FROM chatbot_conversations
                WHERE user_rating IS NOT NULL
                  AND created_at >= :start_date AND created_at <= :end_date
            """,
            "conversion_funnel_visitors": """
                SELECT COUNT(DISTINCT session_id) as total_visitors
                FROM user_behaviors
                WHERE session_start >= :start_date AND session_start <= :end_date
            """,
            "conversion_funnel_register_visits": """
                SELECT COUNT(DISTINCT user_session) as visited_register
                FROM analytics_events
                WHERE page_url LIKE '%register%'
                  AND created_at >= :start_date AND created_at <= :end_date
            """,
            "conversion_funnel_registrations": """
                SELECT COUNT(DISTINCT user_session) as started_registration
                FROM analytics_events
                WHERE event_action = 'form_start'
                  AND event_category = 'registration'
                  AND created_at >= :start_date AND created_at <= :end_date
            """,
            "conversion_funnel_completions": """
                SELECT COUNT(*) as completed_registration
                FROM user_behaviors
                WHERE conversion_action = 'registration'
                  AND session_start >= :start_date AND session_start <= :end_date
            """,
            "conversion_funnel_chatbot_users": """
                SELECT COUNT(DISTINCT session_id) as chatbot_users
                FROM chatbot_conversations
                WHERE created_at >= :start_date AND created_at <= :end_date
            """,
            "user_journey_entry_pages": """
                SELECT entry_page, COUNT(*) as entries
                FROM user_behaviors
                WHERE session_start >= :start_date AND session_start <= :end_date
                  AND entry_page IS NOT NULL
                GROUP BY entry_page
                ORDER BY entries DESC
                LIMIT 10
            """,
            "user_journey_exit_pages": """
                SELECT exit_page, COUNT(*) as exits
                FROM user_behaviors
                WHERE session_start >= :start_date AND session_start <= :end_date
                  AND exit_page IS NOT NULL
                GROUP BY exit_page
                ORDER BY exits DESC
                LIMIT 10
            """,
        }


class APIOptimizer:
    """API Response optimization"""

    @staticmethod
    def compress_response(data):
        """Compress large JSON responses"""
        import gzip
        import json

        json_str = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
        return gzip.compress(json_str.encode("utf-8"))

    @staticmethod
    def paginate_results(query, page=1, per_page=25):
        """Paginate large result sets"""
        return query.paginate(page=page, per_page=per_page, error_out=False)

    @staticmethod
    def optimize_json_response(data):
        """Optimize JSON structure for frontend"""
        optimized = {
            "stats": data.get("stats", {}),
            "charts": {
                "daily": data.get("daily_data", [])[:30],  # Limit to 30 days
                "hourly": data.get("hourly_data", [])[:24],  # 24 hours
                "events": data.get("recent_events", [])[:50],  # Latest 50 events
            },
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "cache_ttl": 300,
                "total_records": len(data.get("all_events", [])),
            },
        }
        return optimized


# Usage Example
def setup_performance_optimizations(app, db):
    """Setup всички performance optimizations"""

    # Initialize caching with Redis fallback
    try:
        cache = AnalyticsCache(app)
        print("✅ Analytics cache initialized successfully")
    except Exception as cache_error:
        print(f"⚠️  Cache initialization failed, using simple cache: {cache_error}")
        # Fallback to simple cache
        app.config["CACHE_TYPE"] = "simple"
        cache = AnalyticsCache(app)

    # Create database indexes
    DatabaseOptimizer.create_analytics_indexes(db)

    # Setup background tasks за cache warming
    import threading

    def warm_cache():
        """Background task за cache warming"""
        while True:
            try:
                # Pre-load common analytics data
                import time

                time.sleep(600)  # Every 10 minutes
                cache.invalidate_analytics_cache()
                # Reload fresh data
            except Exception as e:
                print(f"Cache warming error: {e}")

    # Start background thread
    cache_thread = threading.Thread(target=warm_cache, daemon=True)
    cache_thread.start()

    return cache


# Configuration за production
PERFORMANCE_CONFIG = {
    "CACHE_TYPE": "redis",  # Use Redis в production
    "CACHE_REDIS_URL": os.getenv("REDIS_URL", "redis://redis:6379/0"),
    "CACHE_DEFAULT_TIMEOUT": 300,
    "CACHE_KEY_PREFIX": "helpchain_analytics_",
    # Database connection pooling
    "SQLALCHEMY_ENGINE_OPTIONS": {
        "pool_size": 10,
        "pool_recycle": 120,
        "pool_pre_ping": True,
        "max_overflow": 20,
    },
    # API Rate limiting
    "RATELIMIT_STORAGE_URL": os.getenv("REDIS_URL", "redis://redis:6379/1"),
    "RATELIMIT_DEFAULT": "100 per hour",
}

if __name__ == "__main__":
    print("🚀 Performance Optimization Module Ready")
    print("Use setup_performance_optimizations(app, db) to initialize")
