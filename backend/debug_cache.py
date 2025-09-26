"""
Quick debug script to check cache behavior in Flask app
"""
import sys
sys.path.insert(0, r'c:\Users\Stella Barbarella\OneDrive\Documents\chatGPT\Projet BG\HelpChain\backend')

import appy
from simple_cache import cache_instance

print("🧐 DEBUG: Cache Investigation")
print("=" * 40)

app = appy.app

# Test 1: Check if cache works in Flask context
with app.app_context():
    print(f"1️⃣ Cache instance ID: {id(cache_instance)}")
    
    # Set a test value
    cache_instance.set('debug_test', {'test': 'data'}, 300)
    print("✅ Test value set in cache")
    
    # Get it back immediately
    result = cache_instance.get('debug_test')
    print(f"✅ Test value retrieved: {result}")
    
    # Check stats
    stats = cache_instance.stats()
    print(f"📊 Cache stats: {stats}")

# Test 2: Simulate what happens in API call
print(f"\n2️⃣ Testing cache key generation...")
import hashlib
import json

cache_key_data = {
    'endpoint': 'analytics-data',
    'args': [('days', '7')]
}
cache_key = hashlib.md5(json.dumps(cache_key_data, sort_keys=True).encode()).hexdigest()
print(f"🔑 Cache key: {cache_key}")

# Set data with this key
test_data = {'message': 'This is cached data'}
cache_instance.set(cache_key, test_data, 300)
print("✅ Data cached with API-style key")

# Try to retrieve it
cached_result = cache_instance.get(cache_key)
print(f"✅ Retrieved from cache: {cached_result}")

print(f"\n📊 Final cache stats: {cache_instance.stats()}")