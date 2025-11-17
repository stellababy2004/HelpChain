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

try:
    from flask_caching import Cache
except ImportError:
    Cache = None


class AnalyticsCache:
    def __init__(self, app=None):
        self.cache = None
        if app:
            self.init_app(app)

    def init_app(self, app):
        """Initialize the cache with the Flask app"""

        try:
            # Configure cache with Redis URL
            cache_config = PERFORMANCE_CONFIG.copy()
            app.config.update(cache_config)
            self.cache = Cache(app)
            print("Cache initialized successfully")

        except Exception as e:
            # If anything fails, fallback to simple cache
            print(f"Cache initialization failed ({e}), using simple fallback")
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
                    print("Cache not initialized, calling function directly")
                    return f(*args, **kwargs)

                # Създай unique cache key от параметрите
                try:
                    cache_key = (
                        f"analytics_{f.__name__}_{hash(str(sorted(kwargs.items())))}"
                    )
                except Exception as key_error:
                    # Fallback cache key if hashing fails
                    cache_key = f"analytics_{f.__name__}_fallback_{id(f)}"

                # Провери дали има cached версия
                try:
                    result = self.cache.get(cache_key)
                    if result is not None:
                        print(f"Cache HIT for {cache_key}")
                        return result
                    else:
                        print(f"Cache MISS for {cache_key}")
                except Exception as cache_error:
                    print(f"Cache read error: {cache_error}")
                    # Continue without cache

                # Call the function
                print(f"Calling function {f.__name__} (cache miss)")
                result = f(*args, **kwargs)

                # Try to cache the result
                try:
                    cache_timeout = (
                        timeout if timeout is not None else self.cache.default_timeout
                    )
                    self.cache.set(cache_key, result, timeout=cache_timeout)
                    print(f"Cached result for {cache_key} (timeout: {cache_timeout}s)")
                except Exception as cache_error:
                    print(f"Cache write error: {cache_error}")
                    # Continue without caching

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
            from sqlalchemy import inspect, text

            # Use an explicit connection when creating an inspector so the
            # underlying DBAPI connection is closed promptly. Passing a
            # Connection to inspect() avoids leaving raw sqlite3.Connection
            # objects open in some SQLAlchemy versions.
            with db.engine.connect() as _conn:
                inspector = inspect(_conn)
                existing_tables = set(inspector.get_table_names())

            index_statements = {
                "analytics_events": [
                    (
                        "idx_analytics_timestamp",
                        """
                            CREATE INDEX IF NOT EXISTS idx_analytics_timestamp
                            ON analytics_events(created_at DESC)
                        """,
                    ),
                    (
                        "idx_analytics_event_type",
                        """
                            CREATE INDEX IF NOT EXISTS idx_analytics_event_type
                            ON analytics_events(event_type)
                        """,
                    ),
                    (
                        "idx_analytics_category",
                        """
                            CREATE INDEX IF NOT EXISTS idx_analytics_category
                            ON analytics_events(event_category)
                        """,
                    ),
                    (
                        "idx_analytics_composite",
                        """
                            CREATE INDEX IF NOT EXISTS idx_analytics_composite
                            ON analytics_events(created_at DESC, event_type, event_category)
                        """,
                    ),
                ],
                "user_behaviors": [
                    (
                        "idx_user_behaviors_session_start",
                        """
                            CREATE INDEX IF NOT EXISTS idx_user_behaviors_session_start
                            ON user_behaviors(session_start DESC)
                        """,
                    )
                ],
                "performance_metrics": [
                    (
                        "idx_performance_metrics_timestamp",
                        """
                            CREATE INDEX IF NOT EXISTS idx_performance_metrics_timestamp
                            ON performance_metrics(created_at DESC)
                        """,
                    )
                ],
                "chatbot_conversations": [
                    (
                        "idx_chatbot_conversations_timestamp",
                        """
                            CREATE INDEX IF NOT EXISTS idx_chatbot_conversations_timestamp
                            ON chatbot_conversations(created_at DESC)
                        """,
                    )
                ],
                "users": [
                    (
                        "idx_users_role",
                        """
                            CREATE INDEX IF NOT EXISTS idx_users_role
                            ON users(role)
                        """,
                    ),
                    (
                        "idx_users_created_at",
                        """
                            CREATE INDEX IF NOT EXISTS idx_users_created_at
                            ON users(created_at DESC)
                        """,
                    ),
                    (
                        "idx_users_is_active",
                        """
                            CREATE INDEX IF NOT EXISTS idx_users_is_active
                            ON users(is_active)
                        """,
                    ),
                ],
                "admin_users": [
                    (
                        "idx_admin_users_username",
                        """
                            CREATE INDEX IF NOT EXISTS idx_admin_users_username
                            ON admin_users(username)
                        """,
                    ),
                    (
                        "idx_admin_users_email",
                        """
                            CREATE INDEX IF NOT EXISTS idx_admin_users_email
                            ON admin_users(email)
                        """,
                    ),
                    (
                        "idx_admin_users_role",
                        """
                            CREATE INDEX IF NOT EXISTS idx_admin_users_role
                            ON admin_users(role)
                        """,
                    ),
                    (
                        "idx_admin_users_created_at",
                        """
                            CREATE INDEX IF NOT EXISTS idx_admin_users_created_at
                            ON admin_users(created_at DESC)
                        """,
                    ),
                    (
                        "idx_admin_users_is_active",
                        """
                            CREATE INDEX IF NOT EXISTS idx_admin_users_is_active
                            ON admin_users(is_active)
                        """,
                    ),
                ],
                "volunteers": [
                    (
                        "idx_volunteers_location",
                        """
                            CREATE INDEX IF NOT EXISTS idx_volunteers_location
                            ON volunteers(location)
                        """,
                    ),
                    (
                        "idx_volunteers_is_active",
                        """
                            CREATE INDEX IF NOT EXISTS idx_volunteers_is_active
                            ON volunteers(is_active)
                        """,
                    ),
                    (
                        "idx_volunteers_created_at",
                        """
                            CREATE INDEX IF NOT EXISTS idx_volunteers_created_at
                            ON volunteers(created_at DESC)
                        """,
                    ),
                    (
                        "idx_volunteers_points",
                        """
                            CREATE INDEX IF NOT EXISTS idx_volunteers_points
                            ON volunteers(points DESC)
                        """,
                    ),
                ],
                "help_requests": [
                    (
                        "idx_help_requests_status",
                        """
                            CREATE INDEX IF NOT EXISTS idx_help_requests_status
                            ON help_requests(status)
                        """,
                    ),
                    (
                        "idx_help_requests_created_at",
                        """
                            CREATE INDEX IF NOT EXISTS idx_help_requests_created_at
                            ON help_requests(created_at DESC)
                        """,
                    ),
                    (
                        "idx_help_requests_priority",
                        """
                            CREATE INDEX IF NOT EXISTS idx_help_requests_priority
                            ON help_requests(priority)
                        """,
                    ),
                    (
                        "idx_help_requests_user_id",
                        """
                            CREATE INDEX IF NOT EXISTS idx_help_requests_user_id
                            ON help_requests(user_id)
                        """,
                    ),
                ],
                "tasks": [
                    (
                        "idx_tasks_status",
                        """
                            CREATE INDEX IF NOT EXISTS idx_tasks_status
                            ON tasks(status)
                        """,
                    ),
                    (
                        "idx_tasks_assigned_to",
                        """
                            CREATE INDEX IF NOT EXISTS idx_tasks_assigned_to
                            ON tasks(assigned_to)
                        """,
                    ),
                    (
                        "idx_tasks_created_at",
                        """
                            CREATE INDEX IF NOT EXISTS idx_tasks_created_at
                            ON tasks(created_at DESC)
                        """,
                    ),
                    (
                        "idx_tasks_category",
                        """
                            CREATE INDEX IF NOT EXISTS idx_tasks_category
                            ON tasks(category)
                        """,
                    ),
                    (
                        "idx_tasks_priority",
                        """
                            CREATE INDEX IF NOT EXISTS idx_tasks_priority
                            ON tasks(priority)
                        """,
                    ),
                ],
                "chat_messages": [
                    (
                        "idx_chat_messages_room_id",
                        """
                            CREATE INDEX IF NOT EXISTS idx_chat_messages_room_id
                            ON chat_messages(room_id)
                        """,
                    ),
                    (
                        "idx_chat_messages_created_at",
                        """
                            CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at
                            ON chat_messages(created_at DESC)
                        """,
                    ),
                    (
                        "idx_chat_messages_sender_type",
                        """
                            CREATE INDEX IF NOT EXISTS idx_chat_messages_sender_type
                            ON chat_messages(sender_type)
                        """,
                    ),
                ],
                "notifications": [
                    (
                        "idx_notifications_recipient",
                        """
                            CREATE INDEX IF NOT EXISTS idx_notifications_recipient
                            ON notifications(recipient_id, recipient_type)
                        """,
                    ),
                    (
                        "idx_notifications_type",
                        """
                            CREATE INDEX IF NOT EXISTS idx_notifications_type
                            ON notifications(notification_type)
                        """,
                    ),
                    (
                        "idx_notifications_created",
                        """
                            CREATE INDEX IF NOT EXISTS idx_notifications_created
                            ON notifications(created_at DESC)
                        """,
                    ),
                ],
            }

            created_indexes = []
            skipped_tables = []

            for table_name, statements in index_statements.items():
                if table_name not in existing_tables:
                    skipped_tables.append(table_name)
                    continue

                for index_name, ddl in statements:
                    _res = db.session.execute(text(ddl))
                    try:
                        # Close the Result to ensure DBAPI resources are released promptly
                        try:
                            _res.close()
                        except Exception:
                            pass
                    except Exception:
                        pass
                    created_indexes.append(index_name)

            db.session.commit()

            if created_indexes:
                print(
                    "✅ Database indexes verified or created: "
                    + ", ".join(sorted(created_indexes))
                )
            if skipped_tables:
                print(
                    "ℹ️  Skipped index creation for missing tables: "
                    + ", ".join(sorted(skipped_tables))
                )

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

    # Apply database connection pooling settings
    if "SQLALCHEMY_ENGINE_OPTIONS" not in app.config:
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = PERFORMANCE_CONFIG[
            "SQLALCHEMY_ENGINE_OPTIONS"
        ]
        print("✅ Database connection pooling configured")

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
    "CACHE_REDIS_URL": os.getenv("REDIS_URL", "redis://localhost:6379/0"),
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
    "RATELIMIT_STORAGE_URL": os.getenv("REDIS_URL", "redis://localhost:6379/1"),
    "RATELIMIT_DEFAULT": "100 per hour",
}

if __name__ == "__main__":
    print("🚀 Performance Optimization Module Ready")
    print("Use setup_performance_optimizations(app, db) to initialize")
