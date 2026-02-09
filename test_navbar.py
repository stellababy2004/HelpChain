from flask import render_template_string

from backend.helpchain_backend.src.app import create_app

app = create_app()
client = app.test_client()

print("== BASIC GETs ==")

urls = [
    "/",  # main.index
    "/request",  # main.request_category
    "/about",  # main.about
    "/faq",  # main.faq
    "/volunteer_login",  # main.volunteer_login
    "/admin/login",  # admin.admin_login
]

for u in urls:
    r = client.get(u, follow_redirects=False)
    print(f"{u:22} -> {r.status_code}")

print("\n== Render navbar template (BuildError check) ==")
with app.test_request_context("/"):
    try:
        render_template_string('{% include "partials/navbar_public.html" %}')
        print("Navbar render: OK")
    except Exception as e:
        print("Navbar render: FAIL")
        raise
