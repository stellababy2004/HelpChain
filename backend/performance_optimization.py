"""
Performance Optimization для Analytics System
Caching, Database optimization и API improvements
"""
from flask_caching import Cache
from functools import wraps
import json
from datetime import datetime, timedelta
import redis

class AnalyticsCache:
    def __init__(self, app=None):
        self.cache = Cache()
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        app.config.setdefault('CACHE_TYPE', 'simple')
        app.config.setdefault('CACHE_DEFAULT_TIMEOUT', 300)  # 5 minutes
        self.cache.init_app(app)
    
    def cached_analytics_data(self, timeout=300):
        """Decorator за caching на analytics данни"""
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                # Създай unique cache key от параметрите
                cache_key = f"analytics_{f.__name__}_{hash(str(sorted(kwargs.items())))}"
                
                # Провери дали има cached версия
                result = self.cache.get(cache_key)
                if result is None:
                    result = f(*args, **kwargs)
                    self.cache.set(cache_key, result, timeout=timeout)
                
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
            # Index за timestamp queries
            db.engine.execute("""
                CREATE INDEX IF NOT EXISTS idx_analytics_timestamp 
                ON analytics_event(timestamp DESC)
            """)
            
            # Index за event_type filtering
            db.engine.execute("""
                CREATE INDEX IF NOT EXISTS idx_analytics_event_type 
                ON analytics_event(event_type)
            """)
            
            # Index за category filtering  
            db.engine.execute("""
                CREATE INDEX IF NOT EXISTS idx_analytics_category
                ON analytics_event(category)
            """)
            
            # Composite index за common filters
            db.engine.execute("""
                CREATE INDEX IF NOT EXISTS idx_analytics_composite
                ON analytics_event(timestamp DESC, event_type, category)
            """)
            
            print("✅ Analytics database indexes created successfully")
            return True
            
        except Exception as e:
            print(f"❌ Error creating indexes: {e}")
            return False
    
    @staticmethod
    def optimize_queries():
        """Оптимизирани SQL queries за analytics"""
        return {
            'events_by_day': """
                SELECT DATE(timestamp) as date, 
                       COUNT(*) as count,
                       event_type
                FROM analytics_event 
                WHERE timestamp >= ?
                GROUP BY DATE(timestamp), event_type
                ORDER BY date DESC
            """,
            
            'top_pages': """
                SELECT details->>'$.page' as page,
                       COUNT(*) as visits
                FROM analytics_event 
                WHERE event_type = 'page_view'
                  AND timestamp >= ?
                GROUP BY details->>'$.page'
                ORDER BY visits DESC
                LIMIT 10
            """,
            
            'user_behavior': """
                SELECT session_id,
                       COUNT(*) as actions,
                       MIN(timestamp) as session_start,
                       MAX(timestamp) as session_end
                FROM analytics_event
                WHERE timestamp >= ?
                GROUP BY session_id
                HAVING actions > 1
                ORDER BY actions DESC
            """
        }

class APIOptimizer:
    """API Response optimization"""
    
    @staticmethod
    def compress_response(data):
        """Compress large JSON responses"""
        import gzip
        import json
        
        json_str = json.dumps(data, separators=(',', ':'), ensure_ascii=False)
        return gzip.compress(json_str.encode('utf-8'))
    
    @staticmethod
    def paginate_results(query, page=1, per_page=25):
        """Paginate large result sets"""
        return query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
    
    @staticmethod
    def optimize_json_response(data):
        """Optimize JSON structure for frontend"""
        optimized = {
            'stats': data.get('stats', {}),
            'charts': {
                'daily': data.get('daily_data', [])[:30],  # Limit to 30 days
                'hourly': data.get('hourly_data', [])[:24],  # 24 hours
                'events': data.get('recent_events', [])[:50]  # Latest 50 events
            },
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'cache_ttl': 300,
                'total_records': len(data.get('all_events', []))
            }
        }
        return optimized

# Usage Example
def setup_performance_optimizations(app, db):
    """Setup всички performance optimizations"""
    
    # Initialize caching
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
                # cache.invalidate_analytics_cache()
                # Reload fresh data
            except Exception as e:
                print(f"Cache warming error: {e}")
    
    # Start background thread
    cache_thread = threading.Thread(target=warm_cache, daemon=True)
    cache_thread.start()
    
    return cache

# Configuration за production
PERFORMANCE_CONFIG = {
    'CACHE_TYPE': 'redis',  # Use Redis в production
    'CACHE_REDIS_HOST': 'localhost',
    'CACHE_REDIS_PORT': 6379,
    'CACHE_REDIS_DB': 0,
    'CACHE_DEFAULT_TIMEOUT': 300,
    'CACHE_KEY_PREFIX': 'helpchain_analytics_',
    
    # Database connection pooling
    'SQLALCHEMY_ENGINE_OPTIONS': {
        'pool_size': 10,
        'pool_recycle': 120,
        'pool_pre_ping': True,
        'max_overflow': 20
    },
    
    # API Rate limiting
    'RATELIMIT_STORAGE_URL': 'redis://localhost:6379/1',
    'RATELIMIT_DEFAULT': '100 per hour'
}

if __name__ == '__main__':
    print("🚀 Performance Optimization Module Ready")
    print("Use setup_performance_optimizations(app, db) to initialize")