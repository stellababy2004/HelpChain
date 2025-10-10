from appy import app

print("Testing HSTS header...")

with app.test_client() as client:
    # Test HTTPS request
    response = client.get("/", environ_overrides={"wsgi.url_scheme": "https"})
    print("Status:", response.status_code)
    print("HSTS Header:", response.headers.get("Strict-Transport-Security"))

    # Test HTTP request (should not have HSTS)
    response_http = client.get("/", environ_overrides={"wsgi.url_scheme": "http"})
    print("HTTP Status:", response_http.status_code)
    print("HTTP HSTS Header:", response_http.headers.get("Strict-Transport-Security"))
