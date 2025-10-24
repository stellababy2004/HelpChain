import requests
import json

print('🧪 TESTING HELPCHAIN APPLICATION')
print('=' * 50)

# Test 1: Home page
print('\n1. Testing Home Page...')
try:
    response = requests.get('http://127.0.0.1:5000/')
    print(f'   Status: {response.status_code}')
    print(f'   Content length: {len(response.text)} chars')
    print('   ✅ Home page accessible' if response.status_code == 200 else '   ❌ Home page failed')
except Exception as e:
    print(f'   ❌ Home page error: {e}')

# Test 2: Admin login page
print('\n2. Testing Admin Login Page...')
try:
    response = requests.get('http://127.0.0.1:5000/admin_login')
    print(f'   Status: {response.status_code}')
    print('   ✅ Admin login accessible' if response.status_code == 200 else '   ❌ Admin login failed')
except Exception as e:
    print(f'   ❌ Admin login error: {e}')

# Test 3: Chat page
print('\n3. Testing Chat Page...')
try:
    response = requests.get('http://127.0.0.1:5000/chat')
    print(f'   Status: {response.status_code}')
    print('   ✅ Chat page accessible' if response.status_code == 200 else '   ❌ Chat page failed')
except Exception as e:
    print(f'   ❌ Chat page error: {e}')

# Test 4: Chatbot API
print('\n4. Testing Chatbot API...')
try:
    payload = {'message': 'Hello', 'session_id': 'test123'}
    response = requests.post('http://127.0.0.1:5000/api/chatbot/message', json=payload)
    print(f'   Status: {response.status_code}')
    if response.status_code == 200:
        data = response.json()
        print(f'   Response: {data.get("response", "No response")[:100]}...')
        print('   ✅ Chatbot API working')
    else:
        print(f'   ❌ Chatbot API failed: {response.text}')
except Exception as e:
    print(f'   ❌ Chatbot API error: {e}')

print('\n' + '=' * 50)
print('🧪 BASIC ROUTE TESTING COMPLETE')