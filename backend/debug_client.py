from appy import app

app.testing = True
with app.test_client() as c:
    resp = c.get('/admin/api/requests?status=pending')
    print('status:', resp.status_code)
    print('location:', resp.headers.get('Location'))
    print('headers:', dict(resp.headers))
    print('data:', resp.get_data(as_text=True))
