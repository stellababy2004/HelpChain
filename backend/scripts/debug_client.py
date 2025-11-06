from appy import app

app.config['TESTING'] = True
client = app.test_client()
with client.session_transaction() as sess:
    sess['_user_id'] = '1'
    sess['_fresh'] = True

resp = client.get('/admin/api/requests?status=pending')
print('status', resp.status_code)
print('location', resp.headers.get('Location'))
print('data', resp.get_data()[:500])
