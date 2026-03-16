import os
import sys

# Ensure repository root is on sys.path so `backend` package is importable
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

# Ensure legacy top-level import names used by some modules resolve to the
# package-qualified modules (mimics tests' early aliasing in conftest).
import importlib

try:
    sys.modules.setdefault("models", importlib.import_module("backend.models"))
except Exception:
    pass

from backend import appy

app = getattr(appy, "app")
app.config.setdefault("TESTING", True)
print("APP TESTING:", app.config.get("TESTING"))
with app.test_client() as client:
    print("\n--- Initial cookie jar ---")
    for c in client.cookie_jar:
        print("cookie:", c.name, c.value, c.domain, c.path)

    def try_get(path, method="get", data=None):
        fn = getattr(client, method)
        resp = fn(path, data=data, follow_redirects=False)
        print(f"\nREQUEST {method.upper()} {path} -> status={resp.status_code}")
        print(
            "Headers:",
            {k: v for k, v in resp.headers.items() if k in ("Set-Cookie", "Location")},
        )
        try:
            txt = resp.get_data(as_text=True)
            print("Body snippet:", txt[:300].replace("\n", " "))
        except Exception as e:
            print("Body read error", e)
        return resp

    # Check debug endpoints
    try_get("/_admin_session")
    try_get("/_admin_force_login")
    try_get("/_pytest_force_admin_login")

    # Attempt POST to /admin/login with common default credentials
    resp = client.post(
        "/admin/login",
        data={"username": "admin", "password": "test-password"},
        follow_redirects=False,
    )
    print("\nPOST /admin/login status:", resp.status_code)
    print(
        "POST headers:",
        {k: v for k, v in resp.headers.items() if k in ("Set-Cookie", "Location")},
    )
    try:
        print(
            "POST body snippet:", resp.get_data(as_text=True)[:400].replace("\n", " ")
        )
    except Exception:
        pass

    print("\n--- Cookie jar after attempts ---")
    for c in client.cookie_jar:
        print("cookie:", c.name, c.value, c.domain, c.path)

    # Inspect server-side session by attempting a GET to admin and dumping any visible markers
    resp = client.get("/admin/", follow_redirects=False)
    print("\nGET /admin/ status:", resp.status_code)
    print(
        "GET /admin/ headers:",
        {k: v for k, v in resp.headers.items() if k in ("Set-Cookie", "Location")},
    )
    try:
        print(
            "GET /admin/ body snippet:",
            resp.get_data(as_text=True)[:400].replace("\n", " "),
        )
    except Exception:
        pass

print("\nDone")

