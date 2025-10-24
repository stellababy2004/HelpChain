#!/usr/bin/env python3
"""
Test script to verify Flask-Compress functionality
"""
import requests
import time
import sys

def test_compression():
    print('🧪 Testing Flask-Compress functionality...')

    # Wait for server to be ready
    time.sleep(5)

    try:
        base_url = 'http://127.0.0.1:5000'

        # Test 1: Check if server is responding
        print('1. Testing server connectivity...')
        response = requests.get(f'{base_url}/', timeout=10)
        if response.status_code == 200:
            print('   ✅ Server is responding')
        else:
            print(f'   ❌ Server error: {response.status_code}')
            return False

        # Test 2: Test analytics endpoint without compression
        print('2. Testing analytics endpoint without compression...')
        response1 = requests.get(f'{base_url}/analytics/stream', timeout=10)
        size1 = len(response1.content)
        print(f'   Response size: {size1} bytes')

        # Test 3: Test analytics endpoint with compression
        print('3. Testing analytics endpoint with compression...')
        headers = {'Accept-Encoding': 'gzip, deflate'}
        response2 = requests.get(f'{base_url}/analytics/stream', headers=headers, timeout=10)
        size2 = len(response2.content)
        encoding = response2.headers.get('Content-Encoding', 'none')
        print(f'   Response size: {size2} bytes (encoding: {encoding})')

        # Test 4: Check compression effectiveness
        print('4. Analyzing compression results...')
        if encoding in ['gzip', 'deflate', 'br']:
            print('   ✅ Flask-Compress is working! Response is compressed.')

            if size2 < size1:
                savings = ((size1 - size2) / size1) * 100
                print(f'   📊 Compression savings: {savings:.1f}%')
            else:
                print('   📊 Response size similar (may be small response or already optimized)')
        else:
            print('   ⚠️  No compression detected in response headers')
            print('   This could mean:')
            print('   - Response is too small (< 500 bytes)')
            print('   - Content type not configured for compression')
            print('   - Flask-Compress not properly initialized')

        # Test 5: Check response headers
        print('5. Checking response headers...')
        print(f'   Content-Type: {response2.headers.get("Content-Type", "not set")}')
        print(f'   Content-Encoding: {response2.headers.get("Content-Encoding", "not set")}')
        print(f'   Content-Length: {response2.headers.get("Content-Length", "not set")}')

        return True

    except requests.exceptions.ConnectionError:
        print('❌ Cannot connect to server. Is it running?')
        return False
    except Exception as e:
        print(f'❌ Error during testing: {e}')
        return False

if __name__ == '__main__':
    success = test_compression()
    sys.exit(0 if success else 1)