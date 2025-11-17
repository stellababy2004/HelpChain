import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import httpx

try:
    import jwt  # PyJWT
except Exception as e:
    print(
        "PyJWT is required to run this smoke test. pip install PyJWT", file=sys.stderr
    )
    raise

BASE_URL = os.environ.get("HELPCHAIN_BASE_URL", "http://127.0.0.1:5000")
SECRET = os.environ.get(
    "HELPCHAIN_JWT_SECRET", os.environ.get("SECRET_KEY", "change-me")
)
ALG = "HS256"
SMOKE_ADMIN_USER = os.environ.get("HELPCHAIN_SMOKE_ADMIN_USER", "admin")
SMOKE_ADMIN_PASS = os.environ.get("HELPCHAIN_SMOKE_ADMIN_PASS", "secret123")
SMOKE_USER = os.environ.get("HELPCHAIN_SMOKE_USER", "testuser")
SMOKE_USER_PASS = os.environ.get("HELPCHAIN_SMOKE_USER_PASS", "secret123")


def make_token(role: str) -> str:
    now = int(time.time())
    payload = {
        "sub": f"smoke-{role}",
        "role": role,
        "iat": now,
        "exp": now + 600,
    }
    return jwt.encode(payload, SECRET, algorithm=ALG)


def call(endpoint: str, token: str, **params):
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{BASE_URL}{endpoint}"
    with httpx.Client(timeout=10) as client:
        r = client.get(url, headers=headers, params=params)
        r.raise_for_status()
        return r.json()


def try_login(username: str, password: str) -> str | None:
    url = f"{BASE_URL}/api/login"
    body = {"username": username, "password": password}
    headers = {"Content-Type": "application/json"}
    try:
        with httpx.Client(timeout=10) as client:
            r = client.post(url, headers=headers, content=json.dumps(body))
            if r.status_code == 200:
                data = r.json()
                return data.get("access_token")
    except Exception:
        return None
    return None


def run():
    print("-- Smoke FTS Search --")
    admin_token = try_login(SMOKE_ADMIN_USER, SMOKE_ADMIN_PASS) or make_token("admin")
    user_token = try_login(SMOKE_USER, SMOKE_USER_PASS) or make_token("user")

    # Quick totals
    total_resp = call("/api/requests", admin_token, page=1, page_size=1)
    print("total requests:", total_resp.get("total"))

    # Basic search by common words (should match seeded data)
    data1 = call("/api/requests", admin_token, q="clinic", page=1, page_size=10)
    print(
        "clinic matches (admin):",
        data1.get("total"),
        "items:",
        [d.get("id") for d in data1.get("data", [])],
    )

    # Email search: should match for admin but not for user
    data2 = call("/api/requests", admin_token, q="@example.com", page=1, page_size=10)
    print(
        "email matches (admin):",
        data2.get("total"),
        "items:",
        [d.get("id") for d in data2.get("data", [])],
    )

    data3 = call("/api/requests", user_token, q="@example.com", page=1, page_size=10)
    print(
        "email matches (user):",
        data3.get("total"),
        "items:",
        [d.get("id") for d in data3.get("data", [])],
    )

    # ETag flow sanity (reuse etag should 304 via Invoke-WebRequest; here we just display present)
    print("etag present (admin):", bool(data1.get("etag")))


if __name__ == "__main__":
    try:
        run()
    except httpx.HTTPStatusError as e:
        print(
            "Request failed:", e.response.status_code, e.response.text, file=sys.stderr
        )
        sys.exit(1)
    except Exception as e:
        print("Smoke test error:", repr(e), file=sys.stderr)
        sys.exit(1)
