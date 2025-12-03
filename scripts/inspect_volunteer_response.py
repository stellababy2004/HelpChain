from backend import appy

app = appy.app

with app.test_client() as c:
    # create test data using fixtures present in tests? Instead, call the test setup helper from tests.conftest
    import importlib
    import tests.conftest as conftest

    # Initialize test data via helper in conftest if available
    if hasattr(conftest, 'init_test_data'):
        data = conftest.init_test_data()
    # Fallback: make a GET to /volunteer_dashboard with a session cookie set
    with c.session_transaction() as sess:
        sess['volunteer_logged_in'] = True
        sess['volunteer_id'] = 1
    resp = c.get('/volunteer_dashboard')
    text = resp.get_data(as_text=True)
    print('STATUS', resp.status_code)
    # dump full response to file for manual inspection
    with open('volunteer_response.html', 'w', encoding='utf-8') as f:
        f.write(text)
    print('WROTE volunteer_response.html')
